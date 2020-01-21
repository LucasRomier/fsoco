# -------------------------------------------------------------------------------
# Name:        Object bounding box label tool
# Purpose:     Label object bboxes for ImageNet Detection data
# Author:      Qiushi
# Created:     06/06/2014

# Updated by:  Lucas Romier
# Updated:     07/01/2020

#
# -------------------------------------------------------------------------------
from __future__ import division
from tkinter import *
import tkinter.simpledialog
from PIL import Image, ImageTk
import os
import glob
import random

""" All available classes """
CLASSES = ["blue_cone", "yellow_cone"]
# colors for the bboxes
COLORS = ['blue', 'yellow', 'pink', 'cyan', 'green', 'black']
RENDERING_COLOR = 'red'

IMG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Images')
LABEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Labels')


class BoundingBox(object):
    def __init__(self, img_w, img_h, x, y, w, h, cls_num, id):
        self.img_w = img_w
        self.img_h = img_h
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.cls_num = int(cls_num)
        self.id = id

    def __str__(self):
        return str(self.cls_num) + " " + str(self.x) + " " + str(self.y) + " " + str(self.w) + " " + str(self.h)

    @classmethod
    def from_event(cls, img_w, img_h, x1, y1, x2, y2, cls_num, id):
        dw = 1. / img_w
        dh = 1. / img_h

        x = (x1 + x2) / 2.0
        y = (y1 + y2) / 2.0

        w = x2 - x1
        h = y2 - y1

        x = x * dw
        w = w * dw
        y = y * dh
        h = h * dh
        return cls(img_w, img_h, x, y, w, h, cls_num, id)

    def to_usable(self):
        x = self.x * self.img_w
        w = self.w * self.img_w
        y = self.y * self.img_h
        h = self.h * self.img_h

        x1 = x - (w / 2.0)
        x2 = x + (w / 2.0)
        y1 = y - (h / 2.0)
        y2 = y + (h / 2.0)

        return x1, y1, x2, y2


class LabelTool:
    def __init__(self, master):
        # set up the main frame
        self.parent = master
        self.parent.title("LabelTool")
        self.frame = Frame(self.parent)
        self.frame.pack(fill=BOTH, expand=1)
        self.parent.resizable(width=FALSE, height=FALSE)

        # initialize global state
        self.imageDir = ''
        self.imageList = []
        self.egDir = ''
        self.egList = []
        self.outDir = ''
        self.cur = 0
        self.total = 0
        self.category = ''
        self.imagename = ''
        self.labelfilename = ''
        self.tkimg = None

        # initialize mouse state
        self.STATE = {'click': 0, 'x': 0, 'y': 0}

        # reference to bbox
        self.bboxList = []
        self.bboxId = None
        self.hl = None
        self.vl = None

        # ----------------- GUI stuff ---------------------
        # dir entry & load
        self.label = Label(self.frame, text="Image Dir:")
        self.label.grid(row=0, column=0, sticky=E)
        self.entry = Entry(self.frame)
        self.entry.grid(row=0, column=1, sticky=W + E)
        self.ldBtn = Button(self.frame, text="Load", command=self.loadDir)
        self.ldBtn.grid(row=0, column=2, sticky=W + E)

        # main panel for labeling
        self.mainPanel = Canvas(self.frame, cursor='tcross')
        self.mainPanel.bind("<Button-1>", self.mouseClick)
        self.mainPanel.bind("<Motion>", self.mouseMove)
        self.parent.bind("<Escape>", self.cancelBBox)  # press <Espace> to cancel current bbox
        self.parent.bind("s", self.cancelBBox)
        self.parent.bind("a", self.prevImage)  # press 'a' to go backforward
        self.parent.bind("d", self.nextImage)  # press 'd' to go forward

        self.mainPanel.grid(row=1, column=1, rowspan=4, sticky=W + N)

        scroll_x = Scrollbar(self.frame, orient="horizontal", command=self.mainPanel.xview)
        scroll_x.grid(row=5, column=1, sticky=E + W)
        scroll_y = Scrollbar(self.frame, orient="vertical", command=self.mainPanel.yview)
        scroll_y.grid(row=1, column=2, rowspan=4, sticky=N + S)
        self.mainPanel.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        # showing bbox info & delete bbox
        self.lb1 = Label(self.frame, text='Bounding boxes:')
        self.lb1.grid(row=1, column=3, sticky=W + N)
        self.listbox = Listbox(self.frame, width=22, height=12)
        self.listbox.bind('<<ListboxSelect>>', self.listSelect)
        self.listbox.grid(row=2, column=3, sticky=N)
        self.btnDel = Button(self.frame, text='Delete', command=self.delBBox)
        self.btnDel.grid(row=3, column=3, sticky=W + E + N)
        self.btnClear = Button(self.frame, text='ClearAll', command=self.clearBBox)
        self.btnClear.grid(row=4, column=3, sticky=W + E + N)

        # control panel for image navigation
        self.ctrPanel = Frame(self.frame)
        self.ctrPanel.grid(row=6, column=1, columnspan=2, sticky=W + E)
        self.prevBtn = Button(self.ctrPanel, text='<< Prev', width=10, command=self.prevImage)
        self.prevBtn.pack(side=LEFT, padx=5, pady=3)
        self.nextBtn = Button(self.ctrPanel, text='Next >>', width=10, command=self.nextImage)
        self.nextBtn.pack(side=LEFT, padx=5, pady=3)
        self.progLabel = Label(self.ctrPanel, text="Progress:     /    ")
        self.progLabel.pack(side=LEFT, padx=5)
        self.tmpLabel = Label(self.ctrPanel, text="Go to Image No.")
        self.tmpLabel.pack(side=LEFT, padx=5)
        self.idxEntry = Entry(self.ctrPanel, width=5)
        self.idxEntry.pack(side=LEFT)
        self.goBtn = Button(self.ctrPanel, text='Go', command=self.gotoImage)
        self.goBtn.pack(side=LEFT)

        # display mouse position
        self.disp = Label(self.ctrPanel, text='')
        self.disp.pack(side=RIGHT)

        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(4, weight=1)

    def loadDir(self):
        s = self.entry.get()
        self.parent.focus()
        self.category = s

        # get image list
        self.imageDir = os.path.join(IMG_PATH, '%s' % self.category)
        self.imageDir = self.imageDir.replace("\\", "/")

        self.imageList = [name for name in os.listdir(self.imageDir) if name.endswith(".jpg")]

        if len(self.imageList) == 0:
            print('No .jpg images found in the specified dir!')
            return

        # default to the 1st image in the collection
        self.cur = 1
        self.total = len(self.imageList)

        # set up output dir
        self.outDir = os.path.join(LABEL_PATH, '%s' % self.category)
        self.outDir = self.outDir.replace("\\", "/")
        if not os.path.exists(self.outDir):
            os.mkdir(self.outDir)

        self.loadImage()
        print('%d images loaded from %s' % (self.total, s))

    def loadImage(self):
        # load image
        imagepath = os.path.join(self.imageDir, self.imageList[self.cur - 1])
        imagepath = imagepath.replace("\\", "/")

        self.img = Image.open(imagepath)
        self.img_w = int(self.img.size[0])
        self.img_h = int(self.img.size[1])

        self.tkimg = ImageTk.PhotoImage(self.img)
        self.mainPanel.config(width=400, height=400)
        self.mainPanel.config(scrollregion=(0, 0, self.tkimg.width(), self.tkimg.height()))
        self.mainPanel.config(width=self.tkimg.width(), height=self.tkimg.height())

        self.mainPanel.create_image(0, 0, image=self.tkimg, anchor=NW)
        self.progLabel.config(text="%04d/%04d" % (self.cur, self.total))

        # load labels
        self.clearBBox()
        self.imagename = os.path.split(imagepath)[-1].split('.')[0]
        labelname = self.imagename + '.txt'
        self.labelfilename = os.path.join(self.outDir, labelname)

        if os.path.exists(self.labelfilename):
            with open(self.labelfilename) as f:
                for (i, line) in enumerate(f):
                    split = [float(t.strip()) for t in line.split()]
                    box = BoundingBox(self.img_w, self.img_h, split[1], split[2], split[3], split[4], split[0], "")

                    id = self.mainPanel.create_rectangle(box.to_usable(), width=2, outline=COLORS[int(split[0])])
                    box.id = id
                    self.bboxList.append(box)

                    self.listbox.insert(END, '(%d, %d) -> (%d, %d)' % (box.to_usable()))
                    self.listbox.itemconfig(len(self.bboxList) - 1, fg=COLORS[int(split[0])])

    def saveImage(self):
        with open(self.labelfilename, 'w') as f:
            for bbox in self.bboxList:
                f.write(str(bbox) + "\n")
        print('Image No. %d saved' % self.cur)

    def mouseClick(self, event):
        x = self.mainPanel.canvasx(event.x)
        y = self.mainPanel.canvasy(event.y)

        if self.STATE['click'] == 0:
            self.STATE['x'], self.STATE['y'] = x, y
        else:
            """ Ask user to enter class """
            class_str = "Current classes: "
            for i, cls in enumerate(CLASSES):
                class_str += cls + "(" + str(i) + ") "
            cls_num = tkinter.simpledialog.askinteger("Enter class", class_str)

            if cls_num is not None and cls_num >= 0:
                x1, x2 = min(self.STATE['x'], x), max(self.STATE['x'], x)
                y1, y2 = min(self.STATE['y'], y), max(self.STATE['y'], y)

                self.mainPanel.itemconfig(self.bboxId, outline=COLORS[cls_num])

                """ Add new bbox and convert values """
                self.bboxList.append(BoundingBox.from_event(self.img_w, self.img_h, x1, y1, x2, y2, cls_num, self.bboxId))
                self.bboxId = None

                self.listbox.insert(END, '(%d, %d) -> (%d, %d)' % (x1, y1, x2, y2))
                self.listbox.itemconfig(len(self.bboxList) - 1, fg=COLORS[cls_num])

        self.STATE['click'] = 1 - self.STATE['click']

    def mouseMove(self, event):
        x = self.mainPanel.canvasx(event.x)
        y = self.mainPanel.canvasy(event.y)

        self.disp.config(text='x: %d, y: %d' % (x, y))
        if self.tkimg:
            if self.hl:
                self.mainPanel.delete(self.hl)
            self.hl = self.mainPanel.create_line(0, y, self.tkimg.width(), y, width=2)
            if self.vl:
                self.mainPanel.delete(self.vl)
            self.vl = self.mainPanel.create_line(x, 0, x, self.tkimg.height(), width=2)
        if 1 == self.STATE['click']:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
            self.bboxId = self.mainPanel.create_rectangle(self.STATE['x'], self.STATE['y'], x, y, width=2, outline=RENDERING_COLOR)

    def cancelBBox(self, event):
        if 1 == self.STATE['click']:
            if self.bboxId:
                self.mainPanel.delete(self.bboxId)
                self.bboxId = None
                self.STATE['click'] = 0

    def listSelect(self, event):
        widget = event.widget
        index = int(widget.curselection()[0])
        for i, bbox in enumerate(self.bboxList):
            if i == index:
                self.mainPanel.itemconfig(bbox.id, outline=RENDERING_COLOR)
            else:
                self.mainPanel.itemconfig(bbox.id, outline=COLORS[bbox.cls_num])

    def delBBox(self):
        sel = self.listbox.curselection()
        if len(sel) != 1:
            return
        idx = int(sel[0])
        self.mainPanel.delete(self.bboxList[idx].id)
        self.bboxList.pop(idx)
        self.listbox.delete(idx)

    def clearBBox(self):
        for idx in range(len(self.bboxList)):
            self.mainPanel.delete(self.bboxList[idx].id)
        self.listbox.delete(0, len(self.bboxList))
        self.bboxList = []

    def prevImage(self, event=None):
        self.saveImage()
        if self.cur > 1:
            self.cur -= 1
            self.loadImage()

    def nextImage(self, event=None):
        self.saveImage()
        if self.cur < self.total:
            self.cur += 1
            self.loadImage()

    def gotoImage(self):
        idx = int(self.idxEntry.get())
        if 1 <= idx <= self.total:
            self.saveImage()
            self.cur = idx
            self.loadImage()


if __name__ == '__main__':
    root = Tk()
    tool = LabelTool(root)
    root.resizable(width=True, height=True)
    root.mainloop()
