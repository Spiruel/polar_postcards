from fileinput import filename
import uuid
import streamlit as st
import PIL
from io import BytesIO

import logging
import boto3
from botocore.exceptions import ClientError
import os

import pandas as pd
import uuid

import time

import math
import piexif
import imghdr

import streamlit_authenticator as stauth
import yaml

import subprocess
from datetime import datetime

from suntime import Sun, SunTimeException

codec = 'ISO-8859-1'  # or latin-1

def get_polar_id():
    """return a unique id"""
    return str(uuid.uuid4())

def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def get_sunrise(lat, lon, date):
    """returns the sunrise time for a given location and date"""
    latitude = 51.21
    longitude = 21.01

    sun = Sun(latitude, longitude)
    abd = datetime.date(2014, 10, 3)
    abd_sr = sun.get_local_sunrise_time(abd)
    abd_ss = sun.get_local_sunset_time(abd)

    print('On {} the sun at Warsaw raised at {} and get down at {}.'.
        format(abd, abd_sr.strftime('%H:%M'), abd_ss.strftime('%H:%M')))

    return abd_sr, abd_ss

def distance_from_coord(lat_start, lon_start, lat_end, lon_end):
    """given two coordinates, return the distance between them in kilometres"""
    R = 6371e3
    lat_start = math.radians(lat_start)
    lon_start = math.radians(lon_start)
    lat_end = math.radians(lat_end)
    lon_end = math.radians(lon_end)

    d_lat = lat_end - lat_start
    d_lon = lon_end - lon_start

    a = math.sin(d_lat / 2)**2 + math.cos(lat_start) * math.cos(lat_end) * math.sin(d_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c

    return d

def exif_to_tag(exif_dict):
    """given an exif dictionary, return a tag dictionary"""
    
    exif_tag_dict = {}
    thumbnail = exif_dict.pop('thumbnail')
    exif_tag_dict['thumbnail'] = thumbnail.decode(codec)

    for ifd in exif_dict:
        exif_tag_dict[ifd] = {}
        for tag in exif_dict[ifd]:
            try:
                element = exif_dict[ifd][tag].decode(codec)

            except AttributeError:
                element = exif_dict[ifd][tag]

            exif_tag_dict[ifd][piexif.TAGS[ifd][tag]["name"]] = element

    return exif_tag_dict

def dms_to_dd(gps_coords, gps_coords_ref):
    d, m, s =  gps_coords[0][0],gps_coords[1][0],gps_coords[2][0]
    scale_d, scale_m, scale_s = gps_coords[0][1],gps_coords[1][1],gps_coords[2][1]
    dd = d/scale_d + m/(60*scale_m) + s/(3600*scale_s)

    if gps_coords_ref.upper() in ('S', 'W'):
        return -dd
    elif gps_coords_ref.upper() in ('N', 'E'):
        return dd
    else:
        raise RuntimeError('Incorrect gps_coords_ref {}'.format(gps_coords_ref))

def save_uploadedfile(uploadedfile):
    filesave = os.path.join("tempDir", uploadedfile.name)
    with open(filesave,"wb") as f:
        f.write(uploadedfile.read())
    return filesave #st.success("Saved File:{} to tempDir".format(uploadedfile.name))

def detect_file_type(file):
    """given a file, return the file type"""
    file_type = imghdr.what(file)
    return file_type

def get_video_location(file):
    """given a video file, return the location"""
    # get com.apple.quicktime.location.ISO6709 from mov file

def parse_DegMinSec(data):
    """given a string of coordinates in DegMinSec format, return the coordinates in decimal degrees"""

    from dms2dec.dms_convert import dms2dec
    data = data.replace("deg", "°").replace("min", "'").replace("sec", '"').replace(" ", "").replace("GPSCoordinates:", "")
    data = data.split(',')
    dd_pair = dms2dec(data[0]),dms2dec(data[1])

    return dd_pair

def get_exif_gps_video(path):
    """given a video file, return the gps coordinates"""

    process = subprocess.Popen(["exiftool", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    lines = out.decode("utf-8").split("\n")
    for l in lines:
        if 'GPS Coordinates' in str(l):
            #parse coords
            coords = parse_DegMinSec(l)
            #st.write(coords[::-1])
            return coords

def main():
    st.title("Polar Postcards")

    st.write("""
    
    This is a website to input Polar Postcard information. \n Input your postcard entry below. 

    Upload images or videos for your postcard and we will automatically extract the locations.
    
    Review your submission before clicking the submit button at the end to upload your entry.""")

    name = st.text_input("Name", value=st.session_state["name"])
    entry = st.text_area("Journal entry", "Enter your journal entry")

    date = st.date_input("Date", value=None)

    files = st.file_uploader("Upload images/videos", type=["png", "jpg", "jpeg", "mp4", "avi", "mov"], accept_multiple_files=True)

    st.write("---")
    # if st.button("Submit"):
    # st.success("Submitted")

    st.write("#### Submission text") 
    submission_text = f"""
    Explorer name: {name}\n
Postcard entry: {entry}\n
Date: {date}
    """
    st.code(submission_text)
        
    coords_list = []
    filename_list = []

    st.write("#### Media")
    st.write(f"Number of files uploaded: {len(files)}")
    for num, f in enumerate(files):
        
        media_type = detect_file_type(f)
        st.write(f.name)
        #st.write(f"File {num+1} is a {media_type} file")
        if media_type in ["png", "jpg", "jpeg"]:
            img = PIL.Image.open(BytesIO(f.read()))

            st.image(img, width=300)
            # st.write(img.getexif())
            filename_list.append( f )

            try:
                exif_dict = piexif.load(img.info.get('exif'))
                exif_dict = exif_to_tag(exif_dict)

                # st.write(exif_dict['GPS'])

                coordinates = exif_dict['GPS']

                gps_longitude = dms_to_dd( coordinates['GPSLongitude'], coordinates['GPSLongitudeRef'] )
                gps_latitude = dms_to_dd( coordinates['GPSLatitude'], coordinates['GPSLatitudeRef'] )
                st.info(f'Coordinates for file {num+1}: {gps_longitude:.2f}, {gps_latitude:.2f}')

                coords_list.append((gps_latitude, gps_longitude))
            except Exception as e:
                st.warning("Does not contain any GPS information")
        else:
            st.video(f)
            filename_list.append( f )

            try:
                gps_latitude, gps_longitude = get_exif_gps_video( save_uploadedfile(f) )
                st.info(f'Coordinates for file {num+1}: {gps_longitude:.2f}, {gps_latitude:.2f}')

                coords_list.append((gps_latitude, gps_longitude))
            except Exception as e:
                st.warning("Does not contain any GPS information")

    df = pd.DataFrame(
        coords_list,
        columns=['lat', 'lon'])

    st.write("#### Detected locations")      
    st.map(df)
    
    if st.button('Submit entry'):


        progress_bar = st.progress(0)
        written_files = []
        for num,f in enumerate(filename_list):
            time.sleep(0.1)
            written_files.append(save_uploadedfile(f))
            progress_bar.progress((num+1)/len(filename_list))
            
        # upload files to aws s3
        POLAR_ID = get_polar_id()
        ENTRY_ID = str(uuid.uuid4())

        entry_json = {}
        entry_json['id'] = ENTRY_ID
        entry_json['polar_id'] = POLAR_ID
        entry_json['name'] = name
        entry_json['entry'] = entry
        entry_json['date'] = date
        entry_json['coords'] = coords_list
        entry_json['files'] = written_files

        st.success("Submitted")

        st.write(entry_json)

        s3_upload = False
        if s3_upload:
            # upload to s3
            s3 = boto3.client('s3',
            aws_access_key_id=st.secrets["ACCESS_KEY"],
            aws_secret_access_key=st.secrets["SECRET_KEY"],
            aws_session_token=st.secrets["SESSION_TOKEN"])
            # upload the json payload
            # then upload the media objects one by one and ensure success
            
            for file_name in filename_list:
                bucket = "polar-postcards"
                try:
                    response = s3_client.upload_file(file_name, bucket, file_name)
                    if response == None:
                        st.write(f"Successfully uploaded {file_name} to {bucket}")
                        os.remove(file_name)
                except ClientError as e:
                    st.error(e)
                

# hashed_passwords = stauth.Hasher(['goldfish', '456']).generate()
# st.write(hashed_passwords)

with open('config.yml') as file:
    config = yaml.load(file, Loader=yaml.SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)
name, authentication_status, username = authenticator.login('Login', 'main')

if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'main')
    st.write(f'Welcome *{st.session_state["name"]}*')
    main()
elif st.session_state["authentication_status"] == False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] == None:
    st.warning('Please enter your username and password')
