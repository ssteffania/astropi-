from pathlib import Path
from logzero import logger, logfile
from picamera import PiCamera
from orbit import ISS
from time import sleep
import datetime
from skyfield.api import load
import csv
import numpy as np
import cv2
from pathlib import Path
from PIL import Image, ImageChops


def contrast_stretch(im):
    """
    Function that contrasts a given image
    :param im: the image to be contrasted
    :return: the contrasted image
    """
    in_min = np.percentile(im, 5)
    in_max = np.percentile(im, 95)
    out_min = 0.0
    out_max = 255.0
    out = im - in_min
    out *= ((out_min - out_max) / (in_min - in_max))
    out += in_min
    return out


def calc_ndvi(image):
    """
    Function that calculates the ndvi values for each pixel of an image
    :param image: the given image
    :return: pixel ndvi values
    """
    b, g, r, a = cv2.split(image)
    bottom = (r.astype(float) + b.astype(float))
    bottom[bottom == 0] = 0.01
    ndvi_value = ((b.astype(float) - r) / bottom)
    return ndvi_value


def create_csv_file(data_file):
    """Create a new CSV file and add the header row"""
    with open(data_file, 'w') as f:
        writer = csv.writer(f)
        header = ("Counter", "Date/time", "Latitude", "Longitude")
        writer.writerow(header)
        f.close()


def create_result_file(polaris):
    """Create a new CSV file and add the header row"""
    with open(polaris, 'w') as f:
        writer = csv.writer(f)
        header = ("Counter", "Plant percentage", "Cloud percentage")
        writer.writerow(header)
        f.close()


def create_result_file(polaris):
    """Create a new CSV file and add the header row"""
    with open(polaris, 'a+') as f:
        writer = csv.writer(f)
        header = (
            "Counter", "Upper left quadrant", "Upper right quadrant", "Bottom left quadrant", "Bottom right quadrant")
        writer.writerow(header)
        f.close()


def add_csv_data(polaris, data):
    """Add a row of data to the data_file CSV"""
    with open(polaris, 'a+') as f:
        writer = csv.writer(f)
        writer.writerow(data)
        f.close()


def convert(angle):
    """
    Convert a skyfield Angle to an EXIF-appropriate
    representation (rationals)
    e.g. 98° 34' 58.7 to "98/1,34/1,587/10"

    Return a tuple containing a boolean and the converted angle,
    with the boolean indicating if the angle is negative.
    """
    sign, degrees, minutes, seconds = angle.signed_dms()
    exif_angle = f'{degrees:.0f}/1,{minutes:.0f}/1,{seconds * 10:.0f}/10'
    return sign < 0, exif_angle


def capture(camera, image):
    """Use camera to capture an image file with lat/long EXIF data."""
    location = ISS.coordinates()

    # Convert the latitude and longitude to EXIF-appropriate representations
    south, exif_latitude = convert(location.latitude)
    west, exif_longitude = convert(location.longitude)

    # Set the EXIF tags specifying the current location
    camera.exif_tags['GPS.GPSLatitude'] = exif_latitude
    camera.exif_tags['GPS.GPSLatitudeRef'] = "S" if south else "N"
    camera.exif_tags['GPS.GPSLongitude'] = exif_longitude
    camera.exif_tags['GPS.GPSLongitudeRef'] = "W" if west else "E"

    # Capture the image
    camera.capture(image)


base_folder = Path(__file__).parent.resolve()

# Set a logfile name
logfile(base_folder / "events.log")

lens = Image.open(base_folder / "lens.png")

# Set up camera
cam = PiCamera()
cam.resolution = (4056, 3040)

# Initialise the CSV file
polaris = base_folder / "data.csv"
result_file = base_folder / "results.csv"
create_csv_file(polaris)
create_result_file(result_file)

ephemeris = load('/home/sandbox/de421.bsp')
timescale = load.timescale()
# Initialise the photo counter
counter = 0
computed_photo_count = 0
# Record the start and current time
start_time = datetime.datetime.now()
now_time = datetime.datetime.now()
# Run a loop for (almost) three hours
while now_time < start_time + datetime.timedelta(minutes=170):
    try:
        if ISS.at(timescale.now()).is_sunlit(ephemeris):
            print("Day")
            location = ISS.coordinates()
            # Save the data to the file
            data = (
                counter,
                datetime.datetime.now(),
                location.latitude.degrees,
                location.longitude.degrees,
            )
            add_csv_data(polaris, data)
            # Capture image
            image_file = f"{base_folder}/photo_{counter:03d}.jpg"
            capture(cam, image_file)
            # Log event
            logger.info(f"iteration {counter}")
            counter += 1
            sleep(30)
            # Update the current time
            now_time = datetime.datetime.now()
        else:
            print("Night")
            if computed_photo_count < counter and counter != 0:
                # compute the data

                image = Image.open(f"{base_folder}/photo_{computed_photo_count:03d}.jpg")
                if image.mode == "RGB":
                    image.putalpha(255)
                if lens.mode == "RGB":
                    lens.putalpha(255)
                crop = ImageChops.subtract(lens, image)
                crop = np.array(crop)

                width, height = lens.size

                contrasted = contrast_stretch(crop)
                ndvi = calc_ndvi(contrasted)
                cv2.imwrite(f"{base_folder}/photo_ndvi_{computed_photo_count:03d}.jpg", ndvi)

                # calculate ndvi mean values of the upper left, upper right, lower left and lower right areas of the image,
                # to better localize the polluted plants' area
                nrpixnesanatosistsus = 0
                nrpixsanatosistsus = 0
                nrpixnesanatosistjos = 0
                nrpixsanatosistjos = 0
                nrpixnesanatosidrsus = 0
                nrpixsanatosidrsus = 0
                nrpixnesanatosidrjos = 0
                nrpixsanatosidrjos = 0

                # upper left
                for i in range(0, width // 2):
                    for j in range(0, height // 2):
                        if ndvi[j, i] > 0.1 and ndvi[j, i] < 0.33:
                            nrpixnesanatosistsus = nrpixnesanatosistsus + 1
                        elif ndvi[j, i] >= 0.33:
                            nrpixsanatosistsus = nrpixsanatosistsus + 1
                        else:
                            pass
                if nrpixnesanatosistsus + nrpixsanatosistsus != 0:
                    pollution_factor_stanga_sus = (
                            (nrpixnesanatosistsus / (nrpixnesanatosistsus + nrpixsanatosistsus)) * 100)
                else:
                    pollution_factor_stanga_sus = 0

                # lower left
                for i in range(0, width // 2):
                    for j in range(height // 2, height):
                        if ndvi[j, i] > 0.1 and ndvi[j, i] < 0.33:
                            nrpixnesanatosistjos = nrpixnesanatosistjos + 1
                        elif ndvi[j, i] >= 0.33:
                            nrpixsanatosistjos = nrpixsanatosistjos + 1
                        else:
                            pass
                if nrpixnesanatosistjos + nrpixsanatosistjos != 0:
                    pollution_factor_stanga_jos = (
                            (nrpixnesanatosistjos / (nrpixnesanatosistjos + nrpixsanatosistjos)) * 100)
                else:
                    pollution_factor_stanga_jos = 0

                # upper right
                for i in range(width // 2, width):
                    for j in range(0, height // 2):
                        if ndvi[j, i] > 0.1 and ndvi[j, i] < 0.33:
                            nrpixnesanatosidrsus = nrpixnesanatosidrsus + 1
                        elif ndvi[j, i] >= 0.33:
                            nrpixsanatosidrsus = nrpixsanatosidrsus + 1
                        else:
                            pass
                if nrpixnesanatosidrsus + nrpixsanatosidrsus != 0:
                    pollution_factor_dreapta_sus = (
                            (nrpixnesanatosidrsus / (nrpixnesanatosidrsus + nrpixsanatosidrsus)) * 100)
                else:
                    pollution_factor_dreapta_sus = 0

                # lower right
                for i in range(width // 2):
                    for j in range(height // 2, height):
                        if ndvi[j, i] > 0.1 and ndvi[j, i] < 0.33:
                            nrpixnesanatosidrjos = nrpixnesanatosidrjos + 1
                        elif ndvi[j, i] >= 0.33:
                            nrpixsanatosidrjos = nrpixsanatosidrjos + 1
                        else:
                            pass
                if nrpixnesanatosidrjos + nrpixsanatosidrjos != 0:
                    pollution_factor_dreapta_jos = (
                            (nrpixnesanatosidrjos / (nrpixnesanatosidrjos + nrpixsanatosidrjos)) * 100)
                else:
                    pollution_factor_dreapta_jos = 0

                # write those values to file
                data = (
                    computed_photo_count,
                    pollution_factor_stanga_sus,
                    pollution_factor_dreapta_sus,
                    pollution_factor_stanga_jos,
                    pollution_factor_dreapta_jos
                )
                add_csv_data(result_file, data)
                # Log event
                logger.info(f"computed photo {computed_photo_count}")
                computed_photo_count += 1
            now_time = datetime.datetime.now()
    except Exception as e:
        logger.error(str(e))
