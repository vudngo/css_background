# app.py

from flask import Flask, render_template, request, redirect, url_for
import os
import subprocess
import sys
import pandas as pd
import time
from resemble import Resemble
from pathlib import Path
from pydub import AudioSegment
import json
import csv
from datetime import datetime
import zipfile
import subprocess
import boto3
import logging
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'  # Directory where uploaded files will be stored
ALLOWED_EXTENSIONS = {'csv'}  # Set of allowed file extensions

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    # If user does not select file, browser also submits an empty part without filename
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Run your Python script here
        subprocess.Popen(['python', 'process_csv.py', os.path.join(app.config['UPLOAD_FOLDER'], filename), request.form['api_key'], request.form['project_uuid']])
        return redirect(url_for('index'))
    return redirect(request.url)

if __name__ == '__main__':
    app.run(debug=True)
