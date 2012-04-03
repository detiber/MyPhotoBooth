#!/usr/bin/env python
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
import flickrapi
import datetime
import glib
from multiprocessing import Process, Lock
from xml.etree.ElementTree import Element, ElementTree, dump


class MyPhotoBoothApp(object):
    def __init__(self, config): #numpics=None, archivedir=None, flickrUploader=None):
        self.config = config
        self.archivedir = self.config.archive_dir()
        self.builder = gtk.Builder()
        self.builder.add_from_file("myphotobooth.glade")
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("mainWindow")
        self.imageWindow = self.builder.get_object("imageWindow")
        self.imageWidget = self.builder.get_object("image")
        self.window.show()
        self.window.maximize()
        self.statusbar = self.builder.get_object("statusbar")
        self.emailTextbox = self.builder.get_object("emailTextbox")
        self.index = 0
        self.picturesDisplayed = False
        self.resetDisplay()

    def on_mainWindow_destroy(self, widget):
        gtk.main_quit()

    def on_button_clicked(self, widget):
        print "Email Address: %s" % self.emailTextbox.get_text()
        self.statusbar.push(0, "")
        camera = Camera(self.config)
        camera.takePictures()
        camera = None
        self.processPictures()
        glib.timeout_add_seconds(10, self.resetDisplay)

    def display_picture(self, lock):
        if self.index >= len(self.files):
            print "no more images to display"
            self.picturesDisplayed = True
            time.sleep(5)
            lock.release()
            print "lock released in display_pictures: %s" % lock
            self.resetDisplay()
            return False
        else:
            print "displaying image: %s" % self.files[self.index]
            rect = self.imageWidget.get_allocation()
            self.imageWidget.set_from_pixbuf(
                gtk.gdk.pixbuf_new_from_file_at_scale(self.files[self.index],
                                                      rect.width,
                                                      rect.height, True))
            self.index += 1
            return True

    def processPictures(self):
        tmpdir = tempfile.mkdtemp(prefix="myphotobooth")
        print "created tempdir: %s" % tmpdir
        self.downloadPictures(tmpdir)
 
        # create photostrip and place in tmpdir

        
        # create a lock for process synchronization
        lock = Lock()
        lock.acquire()
        print "lock aquired in processPictures: %s" % lock
        
        # display pictures breifly in order
        self.files = [os.path.join(tmpdir,file) for file in os.listdir(tmpdir)]
        self.files.sort()
        glib.timeout_add_seconds(5, self.display_picture, lock)
        self.imageWindow.show_all()
        self.imageWindow.maximize()
        
        ppProc = Process(target=postProcessPictures,
                            args=(self.files, tmpdir, self.archivedir, self.config, lock))
        ppProc.daemon = True
        ppProc.start()

    def downloadPictures(self, dir):
        os.chdir(dir)
        os.system('gphoto2 -P --force-overwrite')
        os.system('gphoto2 -DR')
        print "files downloaded: %s" % os.listdir(dir)

    def resetDisplay(self):
        if self.picturesDisplayed:
            print "resetting display"
            self.emailTextbox.set_text("")
            self.imageWindow.hide()
            self.imageWidget.clear()
            self.index = 0
            self.picturesDisplayed = False
            self.picturesUploaded = False
            self.picturesEmailed = False
            print "ready for next person"
            self.statusbar.push(0, "Ready")
            # return False so that glib.timeout_add_seconds doesn't fire again
            return False
        # return True so that glib.timeout_add_seconds will fire again
        return True


class Camera(object):
    def __init__(self, config):
        self.config = config
        print 'connecting camera'
        self.conn = pexpect.spawn('ptpcam --chdk', timeout=15)
        check = self.connectionCheck()
        while check == 1:
            check = self.connectionCheck()
    
    def takePictures(self):
        self.conn.sendline('mode 1')
        print 'opening lens'
        time.sleep(5)
        self.conn.expect('<conn>')
        print 'lens opened'
        print "getting ready to take %s pictures" % self.config.num_pics()
        command="lua "
        for i in range(self.config.num_pics()):
            command += "shoot();"
        print "issuing command: %s" % command
        self.conn.sendline(command)
        time.sleep(self.config.num_pics() * 5)
        print '%s pics snapped' % self.config.num_pics()

    def connectionCheck(self):
        print 'testing camera connection'
        self.conn.sendline('r')
        i = self.conn.expect (['<conn>', 'ERROR: Could not open session!', 'ERROR: Could not close session!', '<    >'])
        if i == 0:
            print 'camera connected'
            return 0
        else:
            return 1

    def __del__(self):
        print 'closing camera connection...'
        self.conn.sendline('quit')
        self.conn.expect(pexpect.EOF)
        print 'connection closed'


class FlickrUploader(object):
    def __init__(self, api_key, api_secret, flickr_set):
        self.api_key = api_key
        self.api_secret = api_secret
        self.flickr_set = flickr_set
        self.flickr_set_id = None
        self.flickr = flickrapi.FlickrAPI(self.api_key, self.api_secret)
        (token, frob) = self.flickr.get_token_part_one(perms='write')
        if not token:
            # Update to use a Gui dialog
            raw_input("Press ENTER after you authorized this program")
        self.flickr.get_token_part_two((token, frob))
        print self.flickr_set


    def uploadPictures(self, files):
        urls = []
        for file in files:
            urls.extend(self.uploadPicture(file))
        print "URLs for uploaded pictures: %s" % str(urls)
        return urls

    
    def uploadPicture(self, filename):
        print "Uploading picture to flickr"
        photoid = self.flickr.upload(filename=filename,is_public=1).find('photoid').text
        print "Uploaded picture photoid: %s" % photoid
        if self.flickr_set_id is not None:
            print "Adding photo to existing set: %s %s" % (self.flickr_set,
                                                           self.flickr_set_id)
            self.flickr.photosets_addPhoto(photo_id=photoid,
                                      photoset_id=self.flickr_set_id)
        else:
            print "Getting list of sets"
            for set in self.flickr.photosets_getList().find('photosets').findall('photoset'):
                if set.find('title').text == self.flickr_set:
                    self.flickr_set_id = set.get('id')
                    self.flickr.photosets_addPhoto(photo_id=photoid,
                                                   photoset_id=self.flickr_set_id)
                    print "Adding photoid: %s to Existing set: %s %s" % (photoid,
                                                                         self.flickr_set,
                                                                         self.flickr_set_id)
                    break
            if self.flickr_set_id is None:
                result = self.flickr.photosets_create(title=self.flickr_set, primary_photo_id=photoid)
                self.flickr_set_id = result.find('photoset').get('id')
                print "Added photoid: %s to new set: %s %s" % (photoid,
                                                               self.flickr_set,
                                                               self.flickr_set_id)
        urls = []
        for url in self.flickr.photos_getInfo(photo_id=photoid).find('photo').find('urls').findall('url'):
            urls.append(url.text)
        print "URL(s) for added photo: %s" % str(urls)
        return urls


class Config(object):
    def __init__(self, configfile):
        self.config = ConfigParser.SafeConfigParser(allow_no_value=True)
        self.config.read(configfile)
        
    def use_flickr(self):
        if self.config.get('myphotobooth', 'useFlickr'):
            return True
        else:
            return False

    def flickr_api_key(self):
        if self.use_flickr():
            return self.config.get('myphotobooth', 'flickr_api_key')
        else:
            return None
            
    def flickr_api_secret(self):
        if self.use_flickr():
            return self.config.get('myphotobooth', 'flickr_api_secret')
        else:
            return None

    def flickr_set(self):
        if self.use_flickr():
            return self.config.get('myphotobooth', 'flickr_set')
        else:
            return None

    def num_pics(self):
        return int(self.config.get('myphotobooth', 'numpics'))

    def archive_dir(self):
        return self.config.get('myphotobooth', 'archivedir')


def postProcessPictures(files, tmpdir, archivedir, config, lock):
    # Block until we know that display_pictures has released the lock aquired in
    # process_pictures, then we know that we can safely delete the tmpdir
    lock.acquire()
    lock.release()
    print "lock aquired and released in postProcessPictures: %s" % lock
    flickrurls = None
    if config.use_flickr() is True:
        flickrUploader = FlickrUploader(config.flickr_api_key(),
                                        config.flickr_api_secret(),
                                        config.flickr_set())
        flickrurls = flickrUploader.uploadPictures(files)

    if flickrurls is not None:
        print "Flickr URLs: %s" % str(flickrurls)
    else:
        print "No flickrurls found."


    # email pictures/photostrip from self.files
    
    # archive pictures/photostrip to self.archivedir
    archivePictures(files, tmpdir, archivedir)


def archivePictures(files, tmpdir, archivedir):
    if not os.path.exists(archivedir):
        print "%s not found, creating" % archivedir
        os.makedirs(archivedir)
    print "Moving files to: %s" % archivedir
    for i in range(len(files)):
        newfile = os.path.join(archivedir,
                "photobooth-%s%s.jpg" % (datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"), i))
        shutil.move(files[i], newfile)
    print "removing tempdir: %s" % tmpdir
    shutil.rmtree(tmpdir)


def main():
    config = Config('/etc/myphotobooth.conf')
    app = MyPhotoBoothApp(config)
    gtk.main()


if __name__ == '__main__':
    main()
