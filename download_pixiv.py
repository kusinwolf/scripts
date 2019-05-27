# Standard imports
import argparse
import logging
import re
import subprocess

# Third party imports
import requests


# TODO:
# - Execute Black
# - Fix flake8 errors
# - Check for Already downloaded (Prevent Dups)
# - Windows/Linux Check
# - Add docs on how grab your tokens from your browser
# - Use something other than wget to download so it works in Windows
# - Save/Read tokens from file
# - Possibily logging in via script only


LOGGER = logging.getLogger(__name__)
VERSION = "1.0.0"


ZIP_PAGE = "https://i.pximg.net/img-zip-ugoira/img/{}_ugoira1920x1080.zip"
ARTISTS_PAGE = "https://www.pixiv.net/ajax/user/{}/profile/all"  # API call
IMAGES_PAGE = (
    "https://www.pixiv.net/member_illust.php?mode=medium&illust_id={}"
)
GALLERY_PAGE = (
    "https://www.pixiv.net/bookmark_new_illust.php?p={}"
)


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
        }
    )

    if response.status_code not in range(200, 299):
        print("Failed with status: {}".format(response.status_code))
        return

    # Multi-picture gallery
    if "multiple_illust_viewer" in response.text:
        total_images = int(
            re.compile(
                r""".*pageCount":([0-9]+).*"""
            ).search(response.text).groups()[0]
        )

    # Zip file
    is_zip = "ugoira" in response.text

    if is_zip:
        items = re.compile(
            r"""original":"https://i\.pximg\.net/img-original/img/([0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+)_ugoira0\.[a-z]{3}"\},"""
        ).findall(response.text.replace("\\", ""))
    else:
        items = re.compile(
            r"""original":"(https\://i\.pximg\.net/img-original/img/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+/[0-9]+_p0\.[a-z]{3})"\},"""
        ).findall(response.text.replace("\\", ""))

    if items and is_zip:
        image_link = ZIP_PAGE.format(items[0])
    elif items:
        image_link = items[0].replace("_p0", "_p{}")

    print(items)
    print(image_link)

    x = 0
    while x < total_images and image_link:
        image = image_link.format(x)
        LOGGER.info("Getting: {}".format(image))
        command = " ".join([
            "wget",
            image,
            "--header=\"referer: {}\"".format(
                IMAGES_PAGE.format(illustration_id)
            ),
            "--directory-prefix={}".format(save_to),
        ])
        subprocess.call(command, shell=True)
        x += 1


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
                ARTISTS_PAGE.format(artist_id, page_id)
            )
        }
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
        print("*" * 20)
        print("Artist ID: {} failed".format(artist_id))
        print("*" * 20)


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
        }
    )

    if response.status_code not in range(200, 299):
        print("Failed with status: {}".format(response.status_code))
        return

    text = response.text.replace("&quot;", "\"")
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


if __name__ == "__main__":
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
        "--artists",
        help="The specific artist ids, comma separated",
    )
    parser.add_argument(
        "--illustration_ids",
        help="The specific illustration ids, comma separated",
    )
    parser.add_argument(
        "--pages",
        help="The specific page ids, comma separated or ranges (X-Y]",
    )
    parser.add_argument(
        "--destination",
        dest="save_to",
        help="Where to save the pictures",
        default=r"test",
        type=str,
    )
    args = parser.parse_args()

    if args.illustration_ids:
        illustration_ids = args.illustration_ids.split(",")
        for illustration_id in illustration_ids:
            get_pictures(
                illustration_id=illustration_id,
                save_to=args.save_to,
                device_token=args.device_token,
                php_session_id=args.php_session_id,
            )

    if args.artists:
        artists = args.artists.split(",")
        for artist_id in artists:
            get_artists_gallery(
                artist_id=artist_id,
                save_to=args.save_to,
                device_token=args.device_token,
                php_session_id=args.php_session_id,
            )

    if args.pages:
        pages = args.pages.split(",")
        for page in pages:
            if "-" in page:
                for page in range(*[int(x) for x in page.split("-")]):
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
