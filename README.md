# Imageflipper 

Imageflipper is a program that searches for images using google search and then displays these images continually. I built this program to run on a Raspberry Pi with a small LCD screen. The Pi is mounted on a wall in my study and it brings a continual source of new and exciting images to my eyeballs. In a way, you can think of it as a smart screen saver.

## Features
 * Display images based on configured search terms 
 * View, retrieve, and delete images using the keyboard 
 * Downloads new images periodically in the background and deletes old images as well
 * Blacklists bad urls based on failed image downloads
 * Threads are used so new images are downloaded and old images a cleaned, without disrupting image display
 * Logs requests, errors, etc
 * A daemon also exists for ...
   * Adding new search terms
   * Clearing out old images
   * Downloading new images
   * Listing images that are currently being displayed
   * Showing images that have been downloaded and their disk utilization

## Installation
    git clone https://github.com/fjohnson/imageflipper.git
    cd imageflipper
    pip install pipenv
    pipenv shell
    pipenv install
    *Now edit your config.json file*
    python display.py

## Configuration

This program uses Google's custom search API. You will need two pieces of information, an API key and a search engine ID, which you can get here: [https://developers.google.com/custom-search/v1/introduction](https://developers.google.com/custom-search/v1/introduction)

Next, fill in the `config.json` file. Here's an example. 

    {
    "image_download_interval": 36000,
    "flip_frequency": 5,
    "search_terms": ["garfield"],
    "extra_images": ["pizza","cheese"],
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36"
    "results_per_page": 3
    "search_engine_id": '...'
    "api_key": '...'
    }

And here's what the variables mean.

`image_download_interval`: How often google is queried for new images in seconds  
`flip_frequency`: How long to wait until the next image is shown  
`search_terms`: The terms you want to find images for  
`extra_images`: If you previously downloaded images or you just have images lying around, you can add them to be displayed. Any images in the images/pizza and images/cheese dir will be added in this example.  
`results_per_page`: How many urls are returned in a search? The max is 10.   
`user_agent`: Enter whatever user agent to masquerade here as.   
`api_key`: Your api key  
`search_engine_id`: Your search engine id 

## Run time

Start it up with
	`python display.py`

Defined inputs are:  
  `q` quits  
  `d` force a download of new images   
  `left arrow`: go back an image  
  `right arrow`: go forward an image  
  `i`: show image position out of total  
  `delete`: delete an image from the display buffer and disk 

The daemon is started when display.py is run and by default accepts TCP connections on port 9999. Edit `SearchTermServer.py` to change the port. 

The daemon accepts "raw" tcp connections. No protocol here; open up a tcp connection and start typing. You can accomplish this with PuTTY, telnet, netcat, etc. Once in type `^commands` for the list of options. 

## Screen shots in action

## Ideas for further consideration:
 
* Implement an image comparison algorithm and delete duplicate images. 

	Note: I tested out image comparison using the "Structural Similarity Index" method (see [here](https://www.pyimagesearch.com/2014/09/15/python-compare-two-images/)) but it was too slow. Comparing a newly downloaded image requires a check against every previously downloaded image. If you have hundreds of images, it can be done on the PI, but it can take literally hours. I decided it wasn't worth it in the end. Another option could be a standalone program that runs in the background and cleans up duplicates.

* Display images based on a dictionary of random words instead of predefined keywords.
