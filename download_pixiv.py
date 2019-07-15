# Standard imports
import argparse
import logging
import logging.config
import os
import re
import subprocess
import time

# Third party imports
import requests


# TODO:
# - Use proper logging **
# - Windows/Linux Check
# - Add docs on how grab your tokens from your browser
# - Use something other than wget to download so it works in Windows
# - Save/Read tokens from file
# - Possibily logging in via script only


VERSION = "1.1.1"
CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": (
                "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
            ),
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG",
        }
    },
    "root": {"handlers": ["default"], "level": "DEBUG"}
}
logging.config.dictConfig(CONFIG)
LOGGER = logging.getLogger(__name__)

# Hack until I get the logging working right, stupid thing
LOGGER.error = print
LOGGER.info = print
LOGGER.debug = print

ZIP_PAGE = "https://i.pximg.net/img-zip-ugoira/img/{}_ugoira1920x1080.zip"
ARTISTS_PAGE = "https://www.pixiv.net/ajax/user/{}/profile/all"  # API call
IMAGES_PAGE = (
    "https://www.pixiv.net/member_illust.php?mode=medium&illust_id={}"
)
GALLERY_PAGE = "https://www.pixiv.net/bookmark_new_illust.php?p={}"
DUPLICATES = set()


def get_pictures(illustration_id, save_to, device_token, php_session_id):
    """
    Loads the specific illustration's page and downloads all of the images
    """

    total_images = 1
    image_link = None

    response = requests.get(
        IMAGES_PAGE.format(illustration_id),
        headers={
            "cookie": "PHPSESSID={}; device_token={}".format(
                php_session_id, device_token
            )
        },
    )

    if response.status_code not in range(200, 299):
        LOGGER.error("Failed with status: {}".format(response.status_code))
        return

    # Multi-picture gallery
    if "multiple_illust_viewer" in response.text:
        total_images = int(
            re.compile(r""".*pageCount":([0-9]+).*""")
            .search(response.text)
            .groups()[0]
        )

    # Zip file
    is_zip = "ugoira" in response.text

    if is_zip:
        items = re.compile(
            r"""original":"https://i\.pximg\.net/img-original/img/"""
            + r"([0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+)"
            + r"""_ugoira0\.[a-z]{3}"\},"""
        ).findall(response.text.replace("\\", ""))
    else:
        items = re.compile(
            r"""original":"(https\://i\.pximg\.net/img-original/img/"""
            + r"[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+"
            + r"""_p0\.[a-z]{3})"\},"""
        ).findall(response.text.replace("\\", ""))

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


def get_artists_gallery(artist_id, save_to, device_token, php_session_id):
    """
    Loads the Artist's gallery information and downloads their entire library
    """

    page_id = 1

    response = requests.get(
        ARTISTS_PAGE.format(artist_id, page_id),
        headers={
            "cookie": "PHPSESSID={}; device_token={}; referer={}".format(
                php_session_id,
                device_token,
                ARTISTS_PAGE.format(artist_id, page_id),
            )
        },
    )
    try:
        body = response.json()
        for illustration_id in body["body"]["illusts"].keys():
            get_pictures(
                illustration_id=illustration_id,
                save_to=save_to,
                device_token=device_token,
                php_session_id=php_session_id,
            )
    except Exception as error:
        LOGGER.exception(error)
        LOGGER.error("Artist ID: {} failed".format(artist_id))


def get_pictures_from_gallery(page, save_to, device_token, php_session_id):
    """
    Loads the main page of subscribed artists and pulls all of the listed
    illustrations on that page, then grabs their images
    """

    response = requests.get(
        GALLERY_PAGE.format(page),
        headers={
            "cookie": "PHPSESSID={}; device_token={}".format(
                php_session_id, device_token
            )
        },
    )

    if response.status_code not in range(200, 299):
        LOGGER.error("Failed with status: {}".format(response.status_code))
        return

    text = response.text.replace("&quot;", '"')
    text = text.replace("&gt;", ">")
    text = text.replace("&lt;", "<")
    text = text.replace("&amp;", "&")
    illustration_ids = re.compile(r"""illustId":"([0-9]+)\"""").findall(text)

    for illust_id in illustration_ids:
        get_pictures(
            illustration_id=illust_id,
            save_to=save_to,
            device_token=device_token,
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
            DUPLICATES |= set(files)

    with open("files.txt", "w") as _file:
        _file.write(str(DUPLICATES))

    LOGGER.debug(
        "Completed search in '{}' seconds".format(time.time() - start_time)
    )


def arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Download a images from pixiv via subscriber page numbers, artist "
            + "ids, and/or individual illustration ids\n"
            + "Current version {}".format(VERSION)
        )
    )
    parser.add_argument(
        "--device_token",
        help="The device_token provided by Pixiv",
        required=True,
        type=str,
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
        help="The specific page ids, comma separated or ranges (X-Y]",
    )
    parser.add_argument(
        "--destination",
        default=r"test",
        dest="save_to",
        help="Where to save the pictures",
        type=str,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show debug logs",
    )
    parser.add_argument(
        "--allow_duplicates",
        action="store_true",
        default=False,
        help="While downloading images, allow for duplicates to be downloaded",
    )
    parser.add_argument(
        "--search_directories",
        default=r"test",
        dest="search_directories",
        help="Directories searched to prevent duplicates",
        type=str,
    )
    return parser.parse_args()


def process():
    args = arguments()

    if args.debug:
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
                device_token=args.device_token,
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
                device_token=args.device_token,
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
                        device_token=args.device_token,
                        php_session_id=args.php_session_id,
                    )
            else:
                get_pictures_from_gallery(
                    page=page,
                    save_to=args.save_to,
                    device_token=args.device_token,
                    php_session_id=args.php_session_id,
                )


if __name__ == "__main__":
    process()
