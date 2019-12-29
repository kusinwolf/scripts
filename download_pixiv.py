# Standard imports
import argparse
import json
import logging
import logging.config
import os
import re
import subprocess
import time

# Third party imports
import requests


# TODO:
# - Allow Windows users to run script as executable
# - Add docs on how grab your tokens from your browser
# - Save/Read tokens from file


VERSION = "2.0.2"
CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": (
                "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
            )
        }
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
        }
    },
    "root": {"handlers": ["default"], "level": "INFO"},
}
logging.config.dictConfig(CONFIG)
LOGGER = logging.getLogger(__name__)
DEBUG = False

ZIP_PAGE = "https://i.pximg.net/img-zip-ugoira/img/{}_ugoira1920x1080.zip"
ARTISTS_PAGE = "https://www.pixiv.net/ajax/user/{}/profile/all"  # API call
IMAGES_PAGE = (
    "https://www.pixiv.net/member_illust.php?mode=medium&" + "illust_id={}"
)
GALLERY_PAGE = "https://www.pixiv.net/bookmark_new_illust.php?p={}"
DUPLICATES = set()

# Regex compiles
MULTIPLE_PAGES_SEARCH = re.compile(
    r""".*meta-global-data.*content='(.*)'>.*"""
)
ZIP_IMAGE_SEARCH = re.compile(
    r"""original":"https://i\.pximg\.net/img-original/img/"""
    + r"([0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+)"
    + r"""_ugoira0\.[a-z]{3}"\},"""
)
IMAGE_SEARCH = re.compile(
    r"""original":"(https\://i\.pximg\.net/img-original/"""
    + r"img/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+"
    + r"""_p0\.[a-z]{3})"\},"""
)
ILLUSTRATION_ID_SEARCH = re.compile(r"""illustId":"([0-9]+)\"""")


def get_pictures(illustration_id, save_to, php_session_id):
    """
    Loads the specific illustration's page and downloads all of the
    images
    """

    total_images = 1
    image_link = None
    cookie = "PHPSESSID={};".format(php_session_id)

    response = requests.get(
        IMAGES_PAGE.format(illustration_id), headers={"cookie": cookie}
    )

    if response.status_code not in range(200, 299):
        LOGGER.error("Failed with status: {}".format(response.status_code))
        return

    # Multi-picture gallery
    if "multiple_illust_viewer" in response.text:
        LOGGER.debug("Multiple images in set")
        content = json.loads(
            MULTIPLE_PAGES_SEARCH.search(response.text).groups()[0]
        )
        total_images = content["illust"][str(illustration_id)]["pageCount"]

        LOGGER.debug("Found {} pages".format(total_images))

    # Zip file
    is_zip = "ugoira" in response.text

    if is_zip:
        LOGGER.debug("Found zip item AKA gif")
        items = ZIP_IMAGE_SEARCH.findall(response.text.replace("\\", ""))
    else:
        LOGGER.debug("Not zip/gif item")
        items = IMAGE_SEARCH.findall(response.text.replace("\\", ""))

    if items and is_zip:
        image_link = ZIP_PAGE.format(items[0])
    elif items:
        image_link = items[0].replace("_p0", "_p{}")

    x = 0
    while x < total_images and image_link:
        image = image_link.format(x)
        x += 1

        LOGGER.debug("Attempting: {}".format(image))
        if image.split("/")[-1] in DUPLICATES:
            continue  # Skip the duplicate

        LOGGER.info("Getting: {}".format(image))
        command = " ".join(
            [
                "wget",
                image,
                "--no-verbose",
                '--header="referer: {}"'.format(
                    IMAGES_PAGE.format(illustration_id)
                ),
                "--directory-prefix={}".format(save_to),
            ]
        )
        subprocess.call(command, shell=True)


def get_artists_gallery(artist_id, save_to, php_session_id):
    """
    Loads the Artist's gallery information and downloads their entire
    library
    """

    page_id = 1
    cookie = "PHPSESSID={}; referer={};".format(
        php_session_id, ARTISTS_PAGE.format(artist_id, page_id)
    )

    response = requests.get(
        ARTISTS_PAGE.format(artist_id, page_id), headers={"cookie": cookie}
    )
    try:
        body = response.json()
        LOGGER.debug("Artists Gallery: {}".format(body))
        for illustration_id in body["body"]["illusts"].keys():
            get_pictures(
                illustration_id=illustration_id,
                save_to=save_to,
                php_session_id=php_session_id,
            )
    except Exception as error:
        LOGGER.exception(error)
        LOGGER.error("Artist ID: {} failed".format(artist_id))


def get_pictures_from_gallery(page, save_to, php_session_id):
    """
    Loads the main page of subscribed artists and pulls all of the
    listed illustrations on that page, then grabs their images
    """

    cookie = "PHPSESSID={};".format(php_session_id)

    response = requests.get(
        GALLERY_PAGE.format(page), headers={"cookie": cookie}
    )

    if response.status_code not in range(200, 299):
        LOGGER.error("Failed with status: {}".format(response.status_code))
        return

    text = response.text.replace("&quot;", '"')
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")
    text = text.replace("&amp;", "&")
    illustration_ids = ILLUSTRATION_ID_SEARCH.findall(text)

    for illust_id in illustration_ids:
        get_pictures(
            illustration_id=illust_id,
            save_to=save_to,
            php_session_id=php_session_id,
        )


def build_duplicates_list(directories, allow_duplicates):
    global DUPLICATES

    LOGGER.debug("allow_duplicates: {}".format(allow_duplicates))
    LOGGER.debug("directories: {}".format(directories))
    if allow_duplicates:
        return  # Don't bother searching for dups

    start_time = time.time()

    LOGGER.info("Searching for duplicates in: {}".format(directories))
    for directory in directories:
        for _, _, files in os.walk(directory):
            DUPLICATES = DUPLICATES.union(set(files))

    if DEBUG:
        with open("duplicates.txt", "w") as _file:
            _file.write(str(DUPLICATES))

    LOGGER.debug(
        "Completed search in '{}' seconds".format(time.time() - start_time)
    )


def arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Download a images from pixiv via subscriber page "
            + "numbers, artist ids, and/or individual illustration "
            + "ids\nCurrent version {}".format(VERSION)
        )
    )
    parser.add_argument(
        "--phpsessid",
        dest="php_session_id",
        help="The PHPSESSID provided by Pixiv",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--artists", help="The specific artist ids, comma separated"
    )
    parser.add_argument(
        "--illustrations",
        help="The specific illustration ids, comma separated",
    )
    parser.add_argument(
        "--pages",
        help=("The specific page ids, comma separated or ranges (X-Y]"),
    )
    parser.add_argument(
        "--destination",
        default=r".",
        dest="save_to",
        help="Where to save the pictures",
        type=str,
    )
    parser.add_argument(
        "--debug", action="store_true", default=False, help="Show debug logs"
    )
    parser.add_argument(
        "--allow_duplicates",
        action="store_true",
        default=False,
        help=(
            "While downloading images, allow for duplicates to be "
            + "downloaded"
        ),
    )
    parser.add_argument(
        "--search_directories",
        default=r".",
        dest="search_directories",
        help="Directories searched to prevent duplicates",
        type=str,
    )
    return parser.parse_args()


def process():
    global DEBUG

    args = arguments()

    if args.debug:
        DEBUG = True
        LOGGER.setLevel(logging.DEBUG)

    build_duplicates_list(args.search_directories, args.allow_duplicates)

    if args.illustrations:
        illustration_ids = set(args.illustrations.split(","))
        for illustration_id in illustration_ids:
            if not illustration_id:
                continue  # Skip blanks

            get_pictures(
                illustration_id=illustration_id,
                save_to=args.save_to,
                php_session_id=args.php_session_id,
            )

    if args.artists:
        artists = set(args.artists.split(","))
        for artist_id in artists:
            if not artist_id:
                continue  # Skip blanks

            get_artists_gallery(
                artist_id=artist_id,
                save_to=args.save_to,
                php_session_id=args.php_session_id,
            )

    if args.pages:
        pages = set(args.pages.split(","))
        for page in pages:
            if not page:
                continue  # Skip blanks

            if "-" in page:
                for page in range(*[int(x) for x in page.split("-")]):
                    LOGGER.info("Processing Page {}".format(page))
                    get_pictures_from_gallery(
                        page=page,
                        save_to=args.save_to,
                        php_session_id=args.php_session_id,
                    )
            else:
                get_pictures_from_gallery(
                    page=page,
                    save_to=args.save_to,
                    php_session_id=args.php_session_id,
                )


if __name__ == "__main__":
    process()
