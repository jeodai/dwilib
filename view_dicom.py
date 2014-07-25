#!/usr/bin/env python2

"""View a multi-slice, multi-b-value DWI DICOM image via the matplotlib GUI."""

import argparse
import sys

import numpy as np
import matplotlib.pyplot as plt

import dwi.dicomfile
import dwi.dwimage

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
            description='View DWI DICOM images.')
    p.add_argument('--files', '-f', nargs='*', default=[], required=False,
            help='DICOM files')
    p.add_argument('--verbose', '-v', action='count',
            help='be more verbose')
    args = p.parse_args()
    return args

class Gui(object):
    def __init__(self, image):
        self.image = image
        self.i = 0
        self.j = 0
        self.update = False
        fig = plt.figure()
        fig.canvas.mpl_connect('key_press_event', self.on_key)
        fig.canvas.mpl_connect('button_release_event', self.on_click)
        fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        kwargs = dict(interpolation='nearest',
                vmin=self.image.min(), vmax=self.image.max())
        view = self.image[self.i,:,:,self.j]
        self.im = plt.imshow(view, **kwargs)
        self.show_help()
        plt.show()

    def show_help(self):
        print 'Usage:'
        print '    Click: toggle update mode'
        print '    Move left/right: change slice (in update mode)'
        print '    Move up/down: change b-value (in update mode)'
        print '    b/g/j: select colormap'
        print '    q: quit'

    def on_key(self, event):
        if event.key == 'q':
            plt.close()
        if event.key == 'g':
            plt.set_cmap('gray')
        if event.key == 'j':
            plt.set_cmap('jet')
        if event.key == 'b':
            plt.set_cmap('Blues_r')
        self.redraw(event)

    def on_click(self, event):
        if event.button == 1:
            self.update = not self.update

    def on_motion(self, event):
        if self.update and event.xdata and event.ydata:
            w, h = self.im.get_size()
            relx = event.xdata / w
            rely = event.ydata / h
            self.i = int(relx * self.image.shape[0])
            self.j = int(rely * self.image.shape[-1])
        self.redraw(event)

    def redraw(self, event):
        if event.xdata and event.ydata:
            d = dict(r=int(event.ydata)+1, c=int(event.xdata)+1,
                    s=self.i+1, b=self.j+1)
            s = '\rslice {s:2d}, row {r:3d}, column {c:3d}, b-value {b:2d} '
            sys.stdout.write(s.format(**d))
            sys.stdout.flush()
        view = self.image[self.i,:,:,self.j]
        self.im.set_data(view)
        event.canvas.draw()


args = parse_args()
filenames = args.files

dwimage = dwi.dwimage.load_dicom(filenames)[0]

#plt.switch_backend('gtk')
print dwimage
d = dict(min=dwimage.image.min(), max=dwimage.image.max())
print 'Image intensity min/max: {min}/{max}'.format(**d)
print
Gui(dwimage.image)
