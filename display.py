'''Google image slide show viewer.
Handles downloading, converting, and displaying images.
Images are chosen based on fixed search terms'''

import pygame, os, tempfile, json, sys, random
import urllib, urllib.request, urllib.error, urllib.parse
import threading, time, datetime, re
import hashlib
import signal
import sys
from GIFImage import GIFImage
from pygame import display, image, event, Rect
from PIL import Image
from server import SearchTermServer

pygame.font.init()
CODE_DIR = os.path.dirname(__file__)
IMAGE_DIR = os.path.join(CODE_DIR, "images")
LOAD_IMAGE_DIR = os.path.join(CODE_DIR, "loading_imgs")
#currently the conversion cache never expires while this program is running.
CONVERT_CACHE = {}
display.init()

highest_res = display.list_modes()[0]
SCREEN_WIDTH = 1024 #highest_res[0]
SCREEN_HEIGHT = 768#768 #highest_res[1]
IMAGE_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
FONT_SIZE = 48
FONT_COLOR = (255,255,0)
LOADING_FONT = pygame.font.Font(None, FONT_SIZE)
LOADING_FONT_DETAILED = pygame.font.Font(None, int(FONT_SIZE / 2))
DETAILED_PROGRESS = True
TEXT_PADDING = 5 #px of padding for text

RGB_BLACK = (0,0,0)
MOUSE_LEFT = 1
MOUSE_RIGHT = 3

RESULTS_PER_PAGE = 10 # must be between 1-10
CHUNK_SIZE = 8192
GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1?{}"
MAX_URL_RESULT = 5
SEARCH_TERMS = {'crystals', 'jeans', 'x-men'}
SEARCH_ENGINE_ID = '007957652027458452999:nm6b9xle5se'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36'
#with open("apikey") as apikey_file:
#    API_KEY = apikey_file.readline()
API_KEY = "AIzaSyAtLp1P49VQbGO33Lxie4Un-ZaLLEhvOhw"

IMAGES = set()
IMAGES_EVENT = threading.Event()
IMAGES_EVENT.clear()
IMAGES_DOWNLOAD_INTERVAL = 60 * 60#60 * 60 * 24 #every 24 hrs scan for new images
IMAGE_FLIP_FREQUENCY = 5
IMAGE_SIZES = [
    'xlarge',
    'xxlarge',
    'huge'
]
IMAGE_BLACKLIST_FILENAME = "urlblacklist"
IMAGE_URL_ERRORS = {}
IMAGE_URL_RETRY = 3

MAX_FILE_AGE = 60 * 60 * 24 * 90 # 90 days
IMAGE_CLEAN_INTERVAL = 60*60*24

QUERY_CACHE = {} #key = query, value = search result page index

try:
    with open(IMAGE_BLACKLIST_FILENAME) as blacklist:
        IMAGE_BLACKLIST = {url.strip() for url in blacklist.readlines()}
except IOError:
    IMAGE_BLACKLIST = {}


def assemble_query(query, img_size, index=1):
    parameters = {
        'key': API_KEY,
        'cx': SEARCH_ENGINE_ID,
        'prettyPrint': 'true',
        'searchType': 'image',
        'imgSize': img_size,
        'fields': 'queries(nextPage/totalResults,nextPage/startIndex),items(link)',
        'num': RESULTS_PER_PAGE,
        'q': query,
        'start': index
    }
    return GOOGLE_API_URL.format(urllib.parse.urlencode(parameters))

def assemble_images():
    images = set()
    for term in SEARCH_TERMS:
        img_dir = os.path.join(IMAGE_DIR, term)

        if not os.path.exists(img_dir):
            continue

        for img in os.listdir(img_dir):
            img_full_path = os.path.join(img_dir, img)
            images.add(img_full_path)

    return images

def get_center_width_offset(pil_image):
    iwidth = pil_image.size[0]
    return (SCREEN_WIDTH - iwidth) / 2

def get_center_height_offset(pil_image):
    iheight = pil_image.size[1]
    return (SCREEN_HEIGHT - iheight) / 2

def pil_image_convert(image_path):
    try:
        return Image.open(CONVERT_CACHE[image_path])
    except KeyError:
        pil_image = Image.open(image_path)
        new_pil_image = resize_image(pil_image)

        conv_filepath = tempfile.NamedTemporaryFile(delete=False)
        new_pil_image.save(conv_filepath, format=pil_image.format)
        conv_filepath.close()
        CONVERT_CACHE[image_path] = conv_filepath.name
        pil_image.close()
        return new_pil_image

def resize_image(pil_image):
    width = pil_image.size[0]
    height = pil_image.size[1]

    if width > SCREEN_WIDTH or height > SCREEN_HEIGHT:
        #Shrink image to screen size
        pil_image.thumbnail(IMAGE_SIZE)
        return pil_image

    width_to_screen_ratio = float(SCREEN_WIDTH) / width
    height_to_screen_ratio = float(SCREEN_HEIGHT) / height

    ratio_increase = min(width_to_screen_ratio, height_to_screen_ratio)

    new_width = int(float(width) * ratio_increase)
    new_height = int(float(height) * ratio_increase)

    #Or we return an aspect ratio preserved enlarged image to screen size
    return pil_image.resize((new_width, new_height))

def display_image(image_path):
    pil_image = pil_image_convert(image_path)

    conv_filepath = CONVERT_CACHE[image_path]
    coordinate_x = get_center_width_offset(pil_image)
    coordinate_y = get_center_height_offset(pil_image)
    pil_image.close()

    #returns a surface object. second argument used as name hint
    surface_img = image.load(conv_filepath, image_path)
    screen.fill(RGB_BLACK)
    screen.blit(surface_img, (coordinate_x, coordinate_y))
    display.flip()

def search_for_images(search_term, img_sizes, num_urls_desired=MAX_URL_RESULT):

    urls = set()

    #return if there are no more image sizes to try the search term against
    if not img_sizes:
        print("Ran out of terms to search for {}".format(search_term))
        return urls

    urls_found = 0
    img_size = img_sizes[0]
    next_start_index = QUERY_CACHE.get(search_term+img_size, 1)

    while urls_found < num_urls_desired:
        query_url = assemble_query(search_term, img_size, next_start_index)
        try:
            data = urllib.request.urlopen(query_url).read()
            json_data = json.loads(data)

            if not json_data:
                #json data is empty if there are no more search results so try with another image size
                return urls.union(search_for_images(search_term, img_sizes[1:], num_urls_desired - len(urls)))
            next_start_index = json_data['queries']['nextPage'][0]['startIndex']
            QUERY_CACHE[search_term+img_size] = next_start_index

            for item in json_data['items']:
                link = item['link']

                #filter out x-raw-image:// urls
                if re.match('^https?://', link) and link not in urls and link not in IMAGE_BLACKLIST:
                    filename_hash = hashlib.sha1(link.encode('utf-8')).hexdigest()
                    filepath = os.path.join(IMAGE_DIR, search_term, filename_hash)
                    if filepath not in IMAGES:
                        urls.add(link)
                        urls_found += 1
                        if urls_found == num_urls_desired:
                            break

        except urllib.error.HTTPError as e:
            print('Query Error: {}'.format(query_url))
            print(e)
            return urls
    return urls

def display_loading_progress(search_term, term_url_count, total_urls, urls_processed, term_count):

    percent_complete = (urls_processed/float(total_urls)) * 100
    percent_complete = int(percent_complete)
    msg = "{}%".format(percent_complete)

    loading_font_size = LOADING_FONT.get_ascent()
    text = LOADING_FONT.render(msg, 1, (random.randint(0,255), random.randint(0,255), random.randint(0,255)))
    x_coord = SCREEN_WIDTH - len(msg) * loading_font_size
    y_coord = 0

    screen.fill(RGB_BLACK, Rect(x_coord, y_coord, len(msg) * loading_font_size, loading_font_size + TEXT_PADDING))
    screen.blit(text, (x_coord, y_coord))

    if not DETAILED_PROGRESS:
        display.flip()
        return

    progress_font_size = LOADING_FONT_DETAILED.get_ascent()
    y_coord = SCREEN_HEIGHT - progress_font_size - TEXT_PADDING
    screen.fill(RGB_BLACK, Rect(0, y_coord, SCREEN_WIDTH, progress_font_size + TEXT_PADDING))

    msg = 'Total: {}/{} urls Search Term:"{}":{}/{} urls'.format(urls_processed, total_urls, search_term, term_count, term_url_count)
    text = LOADING_FONT_DETAILED.render(msg, 1, FONT_COLOR)
    screen.blit(text, (0, y_coord))
    display.flip()

def display_file_download_progress(content_length, bytes_read, url, percent_complete):
    if not DETAILED_PROGRESS:
        return

    progress_font_size = LOADING_FONT_DETAILED.get_ascent()
    y_coord_url = SCREEN_HEIGHT - progress_font_size*3 - TEXT_PADDING*3
    y_coord_dl = SCREEN_HEIGHT - progress_font_size*2 - TEXT_PADDING*2
    screen.fill(RGB_BLACK, Rect(0, y_coord_url, SCREEN_WIDTH, progress_font_size + TEXT_PADDING))
    screen.fill(RGB_BLACK, Rect(0, y_coord_dl, SCREEN_WIDTH, progress_font_size + TEXT_PADDING))

    text = LOADING_FONT_DETAILED.render(url, 1, FONT_COLOR)
    screen.blit(text, (0, y_coord_url))

    msg = "Download progress {}B/{}B".format(bytes_read, content_length)
    msg = msg + " {0:.2f}%".format(percent_complete)
    text = LOADING_FONT_DETAILED.render(msg, 1, FONT_COLOR)
    screen.blit(text, (0, y_coord_dl))

    display.flip()

def clear_progress():
    font_size = LOADING_FONT_DETAILED.get_ascent()
    y_coord = SCREEN_HEIGHT - font_size*3 - TEXT_PADDING*3
    height = SCREEN_HEIGHT - y_coord
    screen.fill(RGB_BLACK, Rect(0, y_coord, SCREEN_WIDTH, height))
    display.flip()

def download_file(response, img, url):

    content_length = int(response.info().get('Content-Length').strip())
    bytes_read = 0
    percent_complete = 0

    while True:
        chunk = response.read(CHUNK_SIZE)

        if not chunk:
            return

        bytes_read += len(chunk)
        last_percent_complete = percent_complete
        percent_complete = (bytes_read/float(content_length)) * 100
        img.write(chunk)

        if percent_complete - last_percent_complete > 1:
            display_file_download_progress(content_length, bytes_read, url, percent_complete)

def download_images(term_dict, total_urls):

    urls_processed = 0
    for search_term in term_dict:
        search_images_dir = os.path.join(IMAGE_DIR, search_term)
        if not os.path.exists(search_images_dir):
            os.mkdir(search_images_dir)

        url_count = len(term_dict[search_term])
        for i,url in enumerate(term_dict[search_term]):
            filename_hash = hashlib.sha1(url.encode('utf-8')).hexdigest()
            filename = os.path.join(search_images_dir, filename_hash)
            error = False

            with open(filename, 'wb') as img:
                try:
                    response = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': USER_AGENT}))
                    download_file(response, img, url)
                    IMAGES.add(filename)
                except (urllib.error.HTTPError, urllib.error.URLError, AttributeError) as e:
                    error = True
                    print(e)

                    try:
                        IMAGE_URL_ERRORS[url] += 1
                        if IMAGE_URL_ERRORS[url] == IMAGE_URL_RETRY:
                            IMAGE_BLACKLIST.add(url)
                            print('Blacklisted url:{}'.format(url))
                    except KeyError:
                        IMAGE_URL_ERRORS[url] = 1

            if error and os.path.exists(filename):
                os.unlink(filename)
                print("Failed to download {}".format(url))

            display_loading_progress(search_term, url_count, total_urls, urls_processed, i+1)
            urls_processed += 1


def search_term_download():
    term_dict = {}
    total_urls = 0
    for term in SEARCH_TERMS:
        term_dict[term] = search_for_images(term, IMAGE_SIZES)
        total_urls += len(term_dict[term])

    download_images(term_dict, total_urls)


class ImageDownloader(threading.Thread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.daemon = True

    def run(self):

        while True:
            IMAGES_EVENT.set()
            search_term_download()
            IMAGES_EVENT.clear()
            time.sleep(IMAGES_DOWNLOAD_INTERVAL)


def check_for_exit():
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            end()

def display_loading():
        gifs = os.listdir(LOAD_IMAGE_DIR)
        loading_gif = GIFImage(os.path.join(LOAD_IMAGE_DIR, random.choice(gifs)))

        x_coord = get_center_width_offset(loading_gif.image)
        y_coord = get_center_height_offset(loading_gif.image)

        screen.fill(RGB_BLACK)
        display.flip()
        while True:
            loading_gif.render(screen, (x_coord,y_coord))
            display.flip()

            if not IMAGES_EVENT.isSet():
                return

            check_for_exit()

def idle():
    start = datetime.datetime.now()
    next_tick = datetime.datetime.now()
    input_scan_rate = .1 # sec

    while (next_tick - start).seconds < IMAGE_FLIP_FREQUENCY:
        check_for_exit()
        time.sleep(input_scan_rate)
        next_tick = datetime.datetime.now()

class ImageCleaner(threading.Thread):

    def __init__(self, daemon=True):
        super(self.__class__, self).__init__()
        self.daemon = True

    def run(self):
        global IMAGES

        while True:
            IMAGES_EVENT.set()
            erased_images = set()

            for image in IMAGES:
                age_seconds = os.stat(image).st_mtime
                time_now = time.time()
                if time_now - age_seconds > MAX_FILE_AGE:
                    os.unlink(image)
                    erased_images.add(image)

            if erased_images:
                print("Erased images :{}".format(erased_images))

            IMAGES = IMAGES - erased_images
            IMAGES_EVENT.clear()
            time.sleep(IMAGE_CLEAN_INTERVAL)

def end():
    print('Exiting....')
    for conv_file in CONVERT_CACHE.values():
        os.unlink(conv_file)

    with open(IMAGE_BLACKLIST_FILENAME, 'w') as blacklist:
        for url in IMAGE_BLACKLIST:
            blacklist.write(url+'\n')

    pygame.display.quit()
    pygame.quit()
    sys.exit(0)

def run():
    global SEARCH_TERMS
    global IMAGES

    if not os.path.exists(IMAGE_DIR):
        os.mkdir(IMAGE_DIR)

    IMAGES = assemble_images()

    ImageCleaner().start()
    ImageDownloader().start()

    #wait for the downloader to start
    IMAGES_EVENT.wait()
    display_loading()

    search_term_server = SearchTermServer(IMAGE_DIR, IMAGES, IMAGES_EVENT, search_terms=SEARCH_TERMS)
    search_term_server.start()

    images = set()
    while True:
        SEARCH_TERMS = search_term_server.search_terms
        print("Search Terms: {}".format(SEARCH_TERMS))

        if not IMAGES_EVENT.isSet():
            images = set(IMAGES)

        #No images, so wait until next download time.
        if not images:
            time.sleep(IMAGES_DOWNLOAD_INTERVAL)

        for image in images:
            try:
                display_image(image)
            except IOError:
                continue
            idle()

#This is a surface that can be drawn to like a regular Surface but changes will eventually be seen on the monitor.
screen = display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))#, pygame.FULLSCREEN)
signal.signal(signal.SIGINT,end)
run()
#end()
