'''Google image slide show viewer.
Handles downloading, converting, and displaying images.
Images are chosen based on fixed search terms'''

import pygame, os, tempfile, urllib2, json, sys, random
import threading, shutil, time, datetime
from GIFImage import GIFImage
from pygame import display, image, event, Rect
from PIL import Image

pygame.font.init()
CODE_DIR = os.path.dirname(__file__)
IMAGE_DIR = os.path.join(CODE_DIR, "images")
LOAD_IMAGE_DIR = os.path.join(CODE_DIR, "loading_imgs")
CONVERT_CACHE = {}
display.init()

highest_res = display.list_modes()[0]
SCREEN_WIDTH = 1024 #highest_res[0]
SCREEN_HEIGHT = 1024#768 #highest_res[1]
IMAGE_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
FONT_SIZE = 48
FONT_COLOR = (255,255,0)
LOADING_FONT = pygame.font.Font(None, FONT_SIZE)
LOADING_FONT_DETAILED = pygame.font.Font(None, FONT_SIZE / 2)
DETAILED_PROGRESS = True
TEXT_PADDING = 5 #px of padding for text

RGB_BLACK = (0,0,0)
MOUSE_LEFT = 1
MOUSE_RIGHT = 3

CHUNK_SIZE = 8192
GOOGLE_AJAX_URL = "http://ajax.googleapis.com/ajax/services/search/images?v=1.0&q={}&start={}"
MAX_RESULTS = 5
SEARCH_TERMS = ['vegans']

IMAGES = []
IMAGES_EVENT = threading.Event()
IMAGES_EVENT.clear()
IMAGES_DOWNLOAD_INTERVAL = 5 #60 * 60 * 24 #every 24 hrs scan for new images
IMAGE_FLIP_FREQUENCY = 1

def assemble_images():
    images = []
    for term in SEARCH_TERMS:
        img_dir = os.path.join(IMAGE_DIR, term)

        if not os.path.exists(img_dir):
            continue

        for img in os.listdir(img_dir):
            img_full_path = os.path.join(img_dir, img)
            images.append(img_full_path)

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
        print "Converted {} -> {}".format(pil_image.filename, conv_filepath.name)
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

def get_result_count(search_term):
    index = 0
    url = GOOGLE_AJAX_URL.format(search_term, index)
    data = json.loads(urllib2.urlopen(url).read())
    result_count = int(''.join(data['responseData']['cursor']['resultCount'].split(',')))
    return result_count

def parse_urls(json_data):
    urls = []
    for result in json_data['responseData']['results']:
        urls.append(result['url'])
    return urls

def search_for_images(search_term):
    result_count = get_result_count(search_term)
    if result_count == 0: return []

    urls = []
    for index in range(0, min(MAX_RESULTS, result_count)):
        url = GOOGLE_AJAX_URL.format(search_term, index)
        data = json.loads(urllib2.urlopen(url).read())
        urls.extend(parse_urls(data))

    return set(urls)

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

    content_length = int(response.info().getheader('Content-Length').strip())
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
        search_images_dir = os.path.join(IMAGE_DIR,search_term)
        if not os.path.exists(search_images_dir):
            os.mkdir(search_images_dir)

        url_count = len(term_dict[search_term])
        for i,url in enumerate(term_dict[search_term]):
            filename = os.path.join(search_images_dir, url.rsplit('/')[-1])
            if not os.path.exists(filename):
                error = False
                with open(filename, 'w') as img:
                    try:
                        response = urllib2.urlopen(url)
                        download_file(response, img, url)
                    except urllib2.HTTPError:
                        error = True
                if error and os.path.exists(filename):
                    os.unlink(filename)
                    print "Failed to download {}".format(url)
            display_loading_progress(search_term, url_count, total_urls, urls_processed, i+1)
            urls_processed += 1


def search_term_download():
    term_dict = {}
    total_urls = 0
    for term in SEARCH_TERMS:
        term_dict[term] = search_for_images(term)
        total_urls += len(term_dict[term])

    import pprint
    pprint.pprint(term_dict)
    download_images(term_dict, total_urls)


class ImageDownloader(threading.Thread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.daemon = True

    def run(self):
        global IMAGES

        while True:
            IMAGES_EVENT.set()

            search_term_download()
            IMAGES = assemble_images()

            IMAGES_EVENT.clear()

            time.sleep(IMAGES_DOWNLOAD_INTERVAL)


def check_for_exit(wait=False):
    global DETAILED_PROGRESS

    if wait:
        ev = event.wait()
    else:
        ev = event.poll()

    if ev and ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
        end()
        sys.exit(0)
    elif ev and ev.type == pygame.KEYDOWN and ev.key == pygame.K_DELETE:
        DETAILED_PROGRESS = not DETAILED_PROGRESS
        clear_progress()

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

def run():

    if not os.path.exists(IMAGE_DIR):
        os.mkdir(IMAGE_DIR)

    ImageDownloader().start()

    #wait for the downloader to start
    IMAGES_EVENT.wait()
    display_loading()

    image_index = 0
    images = IMAGES
    display_image(images[image_index])

    while True:
        if not IMAGES_EVENT.isSet():
            images = list(IMAGES)

        for image in images:
            try:
                display_image(image)
            except IOError:
                continue
            idle()

        # ev = event.wait()
        # if ev and ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
        #     return
        # elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == MOUSE_LEFT:
        #     if image_index != len(images) - 1:
        #         image_index += 1
        #     display_image(images[image_index])
        # elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == MOUSE_RIGHT:
        #     if image_index != 0:
        #         image_index -= 1
        #     display_image(images[image_index])

def end():
    for conv_file in CONVERT_CACHE.values():
        os.unlink(conv_file)
    shutil.rmtree(IMAGE_DIR)

def debug():
    display_image(os.path.join(IMAGE_DIR,"ramen1.jpg"))
    while True:
            ev = event.wait()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                return

#This is a surface that can be drawn to like a regular Surface but changes will eventually be seen on the monitor.
screen = display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))#, pygame.FULLSCREEN)
run()
end()
