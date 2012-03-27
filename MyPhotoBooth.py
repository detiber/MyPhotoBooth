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


class MyPhotoBoothApp(object):
    def __init__(self):
        self.builder = gtk.Builder()
        self.builder.add_from_file("myphotobooth.glade")
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("mainWindow")
        self.window.show()
        self.statusbar = self.builder.get_object("statusbar")
        self.emailTextbox = self.builder.get_object("emailTextbox")

    def on_mainWindow_destroy(self, widget):
        gtk.main_quit()

    def on_button_clicked(self, widget):
        print "Go Button clicked"
        print "Email Address: %s" % self.emailTextbox.get_text()
        camera = Camera(self.statusbar)
        camera.takePictures(4)

        #Process pictures here, probably after camera = None to allow gphoto to connect.

        camera = None
        self.resetDisplay()
        print "ready for next person"
        self.statusbar.push(0, "Ready")

    def resetDisplay(self):
        print "resetting display"
        self.emailTextbox.set_text("")

class Camera(object):
    def __init__(self, statusbar):
        self.statusbar = statusbar
        print 'connecting camera'
        self.statusbar.push(0, "Initializing Camera...")
        self.conn = pexpect.spawn('ptpcam --chdk', timeout=15)
        check = self.connectionCheck()
        while check == 1:
            check = self.connectionCheck()

    def takePictures(self, numPics):
        self.conn.sendline('mode 1')
        print 'opening lens'
        time.sleep(5)
        self.conn.expect('<conn>')
        print 'lens opened'
        print "getting ready to take %s pictures" % numPics
        self.statusbar.push(0, "Preparing to take %s pictures" % numPics)
        command="lua "
        for i in range(numPics):
            command += "shoot();"
        print "issuing command: %s" % command
        self.conn.sendline(command)
        time.sleep(numPics * 5)
        print '%s pics snapped' % numPics
        self.statusbar.push(0, "%s pictures taken" % numPics)

    def connectionCheck(self):
        print 'testing camera connection'
        self.statusbar.push(0, "Testing Camera Connection...")
        self.conn.sendline('r')
        i = self.conn.expect (['<conn>', 'ERROR: Could not open session!', 'ERROR: Could not close session!', '<    >'])
        if i == 0:
            print 'camera connected'
            self.statusbar.push(0, "Camera Connected")
            return 0
        else:
            return 1

    def __del__(self):
        print 'closing camera connection...'
        self.statusbar.push(0, "Closing Camera Connection...")
        self.conn.sendline('quit')
        self.conn.expect(pexpect.EOF)
        print 'connection closed'
        self.statusbar.push(0, "Camera Connection Closed")


def main():
    app = MyPhotoBoothApp()
    gtk.main()


if __name__ == '__main__':
    main()
