#    wallpaperGenerator - a program to create a large images from smaller images downloaded from flickr.
#    Copyright (C) 2014  Tim Gendron
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#    
#    Contact:  gendron5000@gmail.com


from bs4 import BeautifulSoup as bs
from PIL import Image, ImageDraw
import flickrapi
import re
import threading
import urllib2
from StringIO import StringIO
import Queue
import random
import math
import xml.etree.ElementTree as ET

# setup some defaults/globals
# urlQu is the queue for the image urls.  disQu is used to keep track of how many image files are found/downloaded/processed.
class Defaults():

	Width = 1920
	Height = 1200
	Threads = 5
	Qu = Queue.Queue()
	urlQu = Queue.Queue()
	disQu = Queue.Queue()

# class of worker threads.  These threads get a url from urlQu, then download the image and queue the image data into Qu
class wrkrThread(threading.Thread):

	def run(self):
		while(1):
			url = Defaults.urlQu.get()
                        # if the url is finished, then the program is shutting down, so break
			if url == 'finished':
				break

			# open the url
			im = urllib2.urlopen( url )
			
			try:
				# actually download image data and queue it
				Defaults.Qu.put(im.read())
				Defaults.disQu.put('w')
			except MemoryError:
				pass
			
                # upon exiting, signal the remaining threads to start shutting down
		Defaults.urlQu.put("finished")

# not currently used, but a work in progress to download images from a different site, in this case, a softer world
class swThread(threading.Thread):

	def run(self):
		baseUrl = "http://www.asofterworld.com/index.php?id="
		highestUrl = 937
		imageText = re.compile('', re.IGNORECASE)

		for i in range (highestUrl):
			newUrl = baseUrl + str(i)
			soup = bs(urllib2.urlopen(newUrl))

			for image in soup.findAll("img"):
				imgUrl = image["src"]
				if not "clean" in imgUrl: continue

				Defaults.urlQu.put( imgUrl )
				Defaults.disQu.put('f')
				break

		Defaults.urlQu.put("finished")


# thread that parses out the images from the flickr API and adds the urls to urlQu.
class flickrThread(threading.Thread):

	def run(self):
                # setup regex object
		flickrSize = re.compile('(large|original)$', re.IGNORECASE)

                # get flickr key
                keyFile = open("flickr_key.txt", 'r')
                key = keyFile.read().strip()
                keyFile.close()

                # setup flickrAPI object, then get the lists of most recent and most interesting pictures
		flickr = flickrapi.FlickrAPI(key, format = 'etree')
		iList = flickr.interestingness_getList()
		nList = flickr.photos_getRecent()

                # find the photos in each list, then merge the two lists
		photos = iList.find('photos').findall('photo')
		photos2 = nList.find('photos').findall('photo')
		photos.extend(photos2)

                # parse out the picture urls.  Make sure that the size is big enough (large/original) before adding to urlQu
		for photo in photos:
			try:
				attrib = flickr.photos_getSizes(photo_id = photo.attrib['id'])
			except:
				continue
			
			sizes = attrib.find('sizes').findall('size')
			for size in sizes:
				if flickrSize.match(size.attrib['label']):
					Defaults.urlQu.put( size.attrib['source'] )
					Defaults.disQu.put('f')
					break
					
		Defaults.urlQu.put("finished")


# thread that puts together the final image from the collection of smaller images.
# the images are rotated a random angle and copied to a random part of the picture
class ProcessImage(threading.Thread):
	
	def run(self):
                # create a huge image, 4x the size of the final image.  The final image will be a centered (both horizontall and vertically)
                # copy of this big image.  The big image is used to make it easy to copy images to without having to worry about copying over the edges
		bigImage = Image.new("RGB", (Defaults().Width*2, Defaults().Height*2), "black")
		size = 1280, 1024
		num =0
		while (1):
			
                        # get image data from queue
			im = Defaults.Qu.get()
			if im == 'finished':
				break           
            
			# set downloaded image data to image object
			image = Image.open( StringIO( im ) )
			#try:
				#image.save(str(num) + '.png')
			#except:
				#print "problem"

                        # scale image down, keeping aspect ratio the same
			image.thumbnail(size, Image.ANTIALIAS)
			picW, picH = image.size
			
                        # get random location image plus random angle between -45 and 45 (don't want sideways/upside-down images)
			width = random.randint(0, Defaults().Width*2) - (picW/2)
			height = random.randint(0, Defaults().Height*2) - (picH/2)
			angle = random.randint(-45, 45)
			
                        # create rotated image mask, then use it to copy just the rotated image to the big image
			binIm = Image.new('1', image.size, 1).rotate(angle, expand=1)
			binW, binH = binIm.size
			bigImage.paste( image.rotate(angle, expand=1) , (width, height), binIm )

                        # need a small black frame around each image - without it, pictures aren't very well defined in the final image
                        # calculate coordinates for all the lines
			angle = math.radians(angle)
			if angle > 0:
				a = ((picW * math.cos(angle)) + width, height)
				b = (binW + width, picH * math.cos(angle) + height)
				c = (picH * math.sin(angle) + width, binH + height)
				d = (width, picW * math.sin(angle) + height)
			elif angle < 0:
				angle = abs(angle)
				a = (picH * math.sin(angle) + width, height)
				b = (binW + width, picW * math.sin(angle) + height)
				c = (picW * math.cos(angle) + width, binH + height)
				d = (width, picH * math.cos(angle) + height)
			elif angle == 0:
				a = (width, height)
				b = (picW + width, height)
				c = (picW + width, picH + height)
				d = (width, picH + height)
			
			coords = (a, b, b, c, c, d, d, a)

                        # then draw all the lines
			draw = ImageDraw.Draw(bigImage)
			draw.line(coords, fill = 'black', width = 10)
			del draw
			
			Defaults.disQu.put('p')
			num+=1
			
			
                # when all images are processed, save the final image 
		bigImage.thumbnail((Defaults().Width, Defaults().Height), Image.ANTIALIAS)
		bigImage.save('bigimage.png')
		Defaults.disQu.put("image saved")
	
class Main():
	def Run(self):
		
                # set the threads up
		ThrFlickr = flickrThread()
		ThrFlickr.start()

		ThrProcessImage = ProcessImage()
		ThrProcessImage.start()
		
		ThrDisplay = Display()
		ThrDisplay.start()
		
                # create worker threads and start them
		Thrwrkr = []
		for i in range(0, Defaults.Threads):
			Thrwrkr.append( wrkrThread() )
			Thrwrkr[i].start()
			Defaults.disQu.put('started wrkrThread[%s]' % (i))
			
                # wait until the flickr thread is finished
		ThrFlickr.join()
		Defaults.disQu.put("FlickR Thread Finished!")
		
                # wait until all the worker threads are finished
		for i in range(0, Defaults.Threads):
			Thrwrkr[i].join()
			Defaults.disQu.put("wrkrThread[%s] finished!" % (i))
		
		Defaults.Qu.put("finished")
		
                # wait until the image processor thread is finished
		ThrProcessImage.join()
		Defaults.disQu.put("finished")
		
# this thread displays the status of the program.  It displays how many images were found/downloaded/processed.
# it will display a total at the end
class Display(threading.Thread):
	def run(self):
		print
		flickr = 0
		download = 0
		processed = 0
		message = ''
		while(1):
			dis = Defaults.disQu.get()
			if dis == 'f':
				flickr = flickr + 1
			elif dis == 'w':
				download = download + 1
			elif dis == 'p':
				processed = processed + 1
			elif dis == 'finished':
				break
			else:
				message = dis
			
			print "\rProcessed / Downloaded / URLs :: %d / %d / %d" %(processed, download, flickr),
		
		print "\nCollege Finished!  Total Image Used: " + str(processed)
		print
