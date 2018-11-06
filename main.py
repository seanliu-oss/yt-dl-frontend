from __future__ import unicode_literals

from kivy.app import App

from kivy.uix.scatter import Scatter
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.checkbox import CheckBox
from kivy.factory import Factory
from kivy.properties import StringProperty
from kivy.properties import NumericProperty
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock, mainthread
import threading

import os

import youtube_dl

class Root(BoxLayout):
    '''
    class Root
        class that defines the root widget
        screen layout defined in yt_dl_frontend.kv
        A pasteButton will paste clipboard to urlInput field
        A clearButton will clear the urlInput field
        The download path is default to /download on windows or /sdcard/download on Android
        Once downButton is pressed, a new thread will be started and invoke youtube_dl
        to start downloading
        Properties:
            saveDir: where to save file
            downStatus: Current status of downloading
            progNum: percentage downloaded
    '''
    if platform == 'win':
        _down_path=os.path.abspath('/download')
    if platform == 'android':
        _down_path=os.path.abspath('/sdcard/download')
    try:
        os.mkdir(_down_path)
    except Exception:
        pass
    saveDir = StringProperty(_down_path)
    downStatus= StringProperty("Waiting for URL")
    progNum=NumericProperty(0)
    
    def download(self,url,audioOnly):
        '''
        download(self,url,audioOnly)
        The main download function, will be started in a seperate thread
        Arguments:
            url: URL to download
            audioOnly: A boolean that defines whether to keep audio only
            Calls the debug, warning and error functions for logging
            Calls prog_book to report download status
        '''
        ydl_opts = {
            'logger': self,
            'progress_hooks': [self.prog_hook],
            'outtmpl':'%(title)s.%(ext)s',
            'ignoreerrors': True,
            'updatetime': False
            #'restrictfilenames': True,
        }
        if audioOnly:
            ydl_opts['format']='bestaudio/best'
            ydl_opts['outtmpl']='%(title)s.mp3'
            ydl_opts['audioformat']='mp3'
        if self._down_path:
            ydl_opts['outtmpl']='/'.join([self._down_path,ydl_opts['outtmpl']])
            print("Output Template:"+ydl_opts['outtmpl'])
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        '''
        error(self,msg)
            A logging function for youtube_dl, will display the error status
            Argument: msg passed in by youtube-dl
        '''
        print(msg)
        self.downStatus= "Oops something went wrong..."+msg[:100]
        self.ids['downButton'].disabled=False
        
    @mainthread
    def prog_hook(self,d):
        '''
        prog_hook(self,d)
            Progress hood for the download
            Use @mainthread decorator to make sure it updates GUI
            Updates wh the progress exceed multiples of 10 to reduce visual updates
            Updates progNum property which will be picked up by progBar 
        
        '''
        if d['status'] == 'downloading':
            self.ids['downButton'].disabled=True
            self.percentDown=int(d['_percent_str'].split('.')[0]) //10 *10
            if self.percentDown > self.previousPercentDown:
                progTxt='{} percent Downloaded'.format(d['_percent_str'])
                print(progTxt)
                self.progNum=self.percentDown
                self.previousPercentDown = self.percentDown
                return
        if d['status'] == 'finished':
            self.downStatus= "Finished..."
            self.previousPercentDown=0
            self.progNum=100
        self.ids['downButton'].disabled=False

    def start_download(self, *args):
        '''
        start_download(self, *args)
            function that gets called when downButton is pressed
            Will start a new thread to download
        '''
        urlInput = self.ids['urlInput']
        url=urlInput.text
        self.downStatus= 'Downloading...'
        self.previousPercentDown=0
        self.progNum=0
        audioOnly=self.ids['audio_only_chkbox'].active
        self.ids['downButton'].disabled=True
        threading.Thread(target=self.download,args=(url,audioOnly)).start()
    
class yt_dl_frontendApp(App):
    pass




if __name__ == "__main__":
    Factory.register('Root', cls=Root)
    yt_dl_frontendApp().run()
