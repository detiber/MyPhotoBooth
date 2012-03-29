#!/usr/bin/python
# -*- coding: utf-8 -*-
# MyPhotoBooth - Photobooth app for CHDK enabled cameras 
#   using ptpcam and gphoto2
#   Loosely based of CHDKPhotobooth by varun
#    (http://code.google.com/p/chdkphotobooth/)
# Author: Jason DeTiberus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pygtk
pygtk.require("2.0")
import gtk
import pexpect
import time
import tempfile
import os
import shutil
import ConfigParser
import logging


class MyPhotoBoothApp(object):
    def __init__(self, numpics=None, archivedir=None):
        if numpics == None:
            self.numpics = 4
        else: 
            self.numpics = numpics
        if archivedir == None:
            self.archivedir = '%s/myphotobooth' % os.getenv("HOME")
        else:
            self.archivedir = archivedir
        self.builder = gtk.Builder()
        self.builder.add_from_file("myphotobooth.glade")
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("mainWindow")
        self.window.show()
        self.statusbar = self.builder.get_object("statusbar")
        self.emailTextbox = self.builder.get_object("emailTextbox")
        self.resetDisplay()

    def on_mainWindow_destroy(self, widget):
        gtk.main_quit()

    def on_button_clicked(self, widget):
        logging.debug("Email Address: %s" % self.emailTextbox.get_text())
        self.statusbar.push(0, "")
        camera = Camera()
        camera.takePictures(self.numpics)
        camera = None
        self.processPictures()
        self.resetDisplay()

    def processPictures(self):
        tmpdir = tempfile.mkdtemp(prefix="myphotobooth")
        logging.debug("created tempdir: %s" % tmpdir)
        self.downloadPictures(tmpdir)

        # display pictures breifly in order
        
        # create photostrip
        
        # display photostrip ( have resetDisplay clear this )

        # archive pictures/photostrip to self.archivedir
        if not os.path.exists(self.archivedir):
            logging.warn("%s not found, creating" % self.archivedir)
            os.makedirs(self.archivedir)
        logging.debug("Moving files to: %s" % self.archivedir)
        for file in os.listdir(tmpdir):
            shutil.move(os.path.join(tmpdir,file),self.archivedir)
        
        # upload pictures/photostrip to Flickr
        
        # email pictures/photostrip
        
        logging.debug("removing tempdir: %s" % tmpdir)
        shutil.rmtree(tmpdir)                

    def downloadPictures(self, dir):
        os.chdir(dir)
        os.system('gphoto2 -P --force-overwrite')
        os.system('gphoto2 -DR')
        logging.debug("files downloaded: %s" % os.listdir(dir))

    def resetDisplay(self):
        logging.debug("resetting display")
        self.emailTextbox.set_text("")
        logging.debug("ready for next person")
        self.statusbar.push(0, "Ready")


class Camera(object):
    def __init__(self):
        logging.debug('connecting camera')
        self.conn = pexpect.spawn('ptpcam --chdk', timeout=15)
        check = self.connectionCheck()
        while check == 1:
            check = self.connectionCheck()
    
    def takePictures(self, numpics):
        self.conn.sendline('mode 1')
        logging.debug('opening lens')
        time.sleep(5)
        self.conn.expect('<conn>')
        logging.debug('lens opened')
        logging.debug("getting ready to take %s pictures" % numpics)
        command="lua "
        for i in range(numpics):
            command += "shoot();"
        logging.debug("issuing command: %s" % command)
        self.conn.sendline(command)
        time.sleep(numpics * 5)
        logging.debug('%s pics snapped' % numpics)

    def connectionCheck(self):
        logging.debug('testing camera connection')
        self.conn.sendline('r')
        i = self.conn.expect (['<conn>', 'ERROR: Could not open session!', 'ERROR: Could not close session!', '<    >'])
        if i == 0:
            logging.debug('camera connected')
            return 0
        else:
            return 1

    def __del__(self):
        logging.debug('closing camera connection...')
        self.conn.sendline('quit')
        self.conn.expect(pexpect.EOF)
        logging.debug('connection closed')


def main():

    config = ConfigParser.SafeConfigParser(allow_no_value=True)
    configfile = '/etc/myphotobooth.conf'
    try:
        config.read(configfile)
        if config.get('myphotobooth', 'debug'):
            debug=logging.DEBUG
        else:
            debug=logging.INFO
        logging.basicConfig(level=debug)

        numpics = config.get('myphotobooth', 'numpics')
        archivedir = config.get('myphotobooth', 'archivedir')
        app = MyPhotoBoothApp(numpics = int(numpics), 
                              archivedir = archivedir)
        gtk.main()
    except ConfigParser.NoSectionError:
        logging.basicConfig()
        logging.warn("Config file %s not found, using defaults" % configfile)
        app = MyPhotoBoothApp()
        gtk.main()
        


if __name__ == '__main__':
    main()
