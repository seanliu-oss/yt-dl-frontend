from kivy.app import App
from kivy.factory import Factory
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, NumericProperty
from kivy.utils import platform
import threading
import os
import yt_dlp


class Root(BoxLayout):
    progNum = NumericProperty(0)
    downStatus = StringProperty("Waiting for URL")
    saveDir = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_android = platform == "android"
        if self.is_android:
            try:
                from android import mActivity
                from android.runnable import run_on_ui_thread
                from plyer import notification
                from android.storage import primary_external_storage_path

                self.run_on_ui_thread = run_on_ui_thread
                _down_path = primary_external_storage_path() + "/download"
            except ImportError as e:
                print(f"Import error: {e}")
                self.run_on_ui_thread = lambda x: x()
                _down_path = "/sdcard/download"
        else:
            self.run_on_ui_thread = lambda x: x()
            _down_path = "/download"

        self.saveDir = os.path.abspath(_down_path)
        try:
            os.mkdir(self.saveDir)
        except Exception:
            pass

    def start_foreground_service(self):
        if self.is_android:
            self.run_on_ui_thread(self._start_foreground_service)()

    def stop_foreground_service(self):
        if self.is_android:
            self.run_on_ui_thread(self._stop_foreground_service)()

    def _start_foreground_service(self):
        from android import api_version
        from android.permissions import Permission, request_permissions

        def callback(permissions, results):
            if all(results):
                print("All permissions granted")
                self._start_foreground()
            else:
                print("Some permissions denied")

        if api_version < 33:
            permissions = [Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
        else:
            permissions = [Permission.READ_MEDIA_VIDEO, Permission.READ_MEDIA_AUDIO]
        request_permissions(permissions, callback)

    def _start_foreground(self):
        from android import mActivity, autoclass, cast
        from jnius import JavaException

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Context = autoclass('android.content.Context')
        PendingIntent = autoclass('android.app.PendingIntent')
        NotificationCompatBuilder = autoclass('androidx.core.app.NotificationCompat$Builder')
        NotificationManagerCompat = autoclass('androidx.core.app.NotificationManagerCompat')

        self.mServiceIntent = Intent(mActivity.getApplicationContext(), PythonActivity)
        self.mServiceIntent.setAction("org.test.yt_dl_frontend.FOREGROUND")
        self.mServicePendingIntent = PendingIntent.getActivity(mActivity, 0, self.mServiceIntent,
                                                               PendingIntent.FLAG_IMMUTABLE)

        channel_id = "yt_dl_channel"
        channel_name = "YT-DL Channel"
        channel_description = "YT-DL Channel Description"
        NotificationManager = autoclass('android.app.NotificationManager')
        NotificationChannel = autoclass('android.app.NotificationChannel')
        notification_service = cast(NotificationManager, mActivity.getSystemService(Context.NOTIFICATION_SERVICE))
        channel = NotificationChannel(channel_id, channel_name, NotificationManager.IMPORTANCE_LOW)
        channel.setDescription(channel_description)
        notification_service.createNotificationChannel(channel)

        builder = NotificationCompatBuilder(mActivity, channel_id)
        builder.setContentTitle("YT-DL Frontend")
        builder.setContentText("Downloading...")
        builder.setSmallIcon(mActivity.getApplicationInfo().icon)
        builder.setContentIntent(self.mServicePendingIntent)
        builder.setOngoing(True)
        self.notification = builder.build()

        notification_manager = NotificationManagerCompat.from_(mActivity)
        notification_manager.notify(1, self.notification)

        try:
            mActivity.startService(self.mServiceIntent)
        except JavaException as e:
            print("Error starting service:", e)

    def _stop_foreground_service(self):
        from android import mActivity, autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        NotificationManagerCompat = autoclass('androidx.core.app.NotificationManagerCompat')

        notification_manager = NotificationManagerCompat.from_(mActivity)
        notification_manager.cancel(1)

        self.mServiceIntent = Intent(mActivity.getApplicationContext(), PythonActivity)
        self.mServiceIntent.setAction("org.test.yt_dl_frontend.STOP_FOREGROUND")
        mActivity.stopService(self.mServiceIntent)

    def download(self, url, audio_only, check_ssl):
        ydl_opts = {
            'logger': self,
            'progress_hooks': [self.prog_hook],
            'outtmpl': '%(title)s.%(ext)s',
            'ignoreerrors': True,
            'updatetime': False,
            'nocheckcertificate': True,
            'verbose': True
        }
        if audio_only:
            ydl_opts['format'] = 'bestaudio[ext=m4a]'
        else:
            # Download the video in the highest resolution available
            ydl_opts['format'] = 'b'

        if check_ssl:
            ydl_opts['nocheckcertificate'] = False
        if self.saveDir:
            ydl_opts['outtmpl'] = os.path.join(self.saveDir, ydl_opts['outtmpl'])
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.downStatus = "Oops something went wrong..." + msg[:300]
        self.ids['downButton'].disabled = False

    def prog_hook(self, d):
        if d['status'] == 'downloading':
            self.downStatus = "Downloading..."
            self.ids['downButton'].disabled = True
            self.percentDown = int(d['_percent_str'].split('.')[0]) // 10 * 10
            if self.percentDown > getattr(self, 'previousPercentDown', 0):
                _pct_str = d['_percent_str']
                progress_text = f'{_pct_str} percent Downloaded'
                print(progress_text)
                self.progNum = self.percentDown
                self.previousPercentDown = self.percentDown
                return
        if d['status'] == 'finished':
            self.downStatus = "Finished..."
            self.previousPercentDown = 0
            self.progNum = 100
            self.stop_foreground_service()
        self.ids['downButton'].disabled = False

    def start_download(self, *args):
        url_input = self.ids['urlInput']
        url = url_input.text
        self.previousPercentDown = 0
        self.progNum = 0
        audio_only = self.ids['audio_only_chkbox'].active
        check_ssl = self.ids['check_cert'].active
        self.ids['downButton'].disabled = True
        self.start_foreground_service()
        threading.Thread(target=self.download, args=(url, audio_only, check_ssl)).start()

    def on_stop(self):
        self.stop_foreground_service()


class yt_dl_frontendApp(App):
    pass


if __name__ == "__main__":
    Factory.register('Root', cls=Root)
    yt_dl_frontendApp().run()
