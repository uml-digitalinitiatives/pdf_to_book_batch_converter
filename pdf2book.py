#!/usr/bin/env python3
# encoding: utf-8
'''
PDF to Islandora Book Batch converter

Created by Jared Whiklo on 2016-03-16.
Copyright (c) 2016 University of Manitoba Libraries. All rights reserved.
''' 
import sys, os
import argparse
import re
import logging, logging.config
import subprocess
import time
import PyPDF2
import html

logger = None
required_programs = [
    {'exec' : 'gs', 'check_var' : '--help'},
    {'exec' : 'tesseract', 'check_var' : '-v'},
    {'exec' : '/usr/local/bin/convert', 'check_var' : '-version' }
]
rxcountpages = re.compile(b"/Type\s*/Page([^s]|$)", re.MULTILINE|re.DOTALL)
options = {'overwrite' : False, 'pdf_password' : '', 'language' : 'eng'}
htmlmatch = re.compile(r'<[^>]+>', re.MULTILINE|re.DOTALL)
blanklines = re.compile(r'^[\x01|\x0a|\s]*$', re.MULTILINE)

'''Parse a PDF and produce derivatives

Keyword arguments
pdf -- The full path to the PDF file
'''
def processPdf(pdf):
    logger.info("Processing {}".format(pdf))
    # Check for an existing directory
    book_name = os.path.splitext(pdf)[0]
    book_dir = os.path.join(os.path.dirname(pdf), book_name + '_dir')
    if not os.path.exists(book_dir):
        os.mkdir(book_dir)

    pages = countPages(pdf)
    logger.debug("counted {} pages in {}".format(pages, pdf))
    
    for p in list(range(1, pages)):
        logger.info("Processing page {}".format(str(p)))
        outDir = os.path.join(book_dir, str(p))
        if not os.path.exists(os.path.join(book_dir, str(p))):
            logger.debug("Creating directory for page {} in {}".format(p, book_dir))
            os.mkdir(os.path.join(book_dir, outDir))
        newPdf = getPdfPage(pdf, p, outDir)
        tiffFile = getTiff(newPdf, outDir)
        hocrFile = getHocr(tiffFile, outDir)
        getOcr(tiffFile, hocrFile, outDir)


'''Produce a single page Tiff from a single page PDF

Keyword arguments
newPdf -- The full path to the PDF file
outDir -- The directory to save the single page Tiff to
'''
def getTiff(newPdf, outDir):
    logger.debug("in getTiff")
    device = 'tiff32nc'
    resolution = 300
    # Increase density by 25%, then resize to only 75%
    altered_resolution = int(resolution * 1.25)
    output_file = os.path.join(outDir, 'OBJ.tiff')
    if os.path.exists(output_file) and os.path.isfile(output_file) and options['overwrite']:
        # Delete the file if it exists AND we set --overwrite
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))
    
    if not os.path.exists(output_file):
        # Only run if the file doesn't exist.
        logger.debug("Generating Tiff")
        #op = ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dUseCropBox', '-sDEVICE={}'.format(device), '-sCompression=lzw', '-r{}'.format(str(resolution)), 
        #    '-sOutputFile={}'.format(output_file), '-dFirstPage={}'.format(str(page)), '-dLastPage={}'.format(str(page)), pdf ]
        op = ['convert', '-density', str(altered_resolution), newPdf, '-resize', '75%', '-colorspace', 'rgb', '-alpha', 'Off', output_file]
        if not doSystemCall(op):
            quit()
    return output_file
            

'''Produce a single page PDF from a multi-page PDF

Keyword arguments
pdf -- The full path to the PDF file
page -- The page to extract
outDir -- The directory to save the single page PDF to

Returns the path to the new PDF file
'''
def getPdfPage(pdf, page, outDir):
    output_file = os.path.join(outDir, 'PDF.pdf')
    if os.path.exists(output_file) and os.path.isfile(output_file) and options['overwrite']:
        # Delete the file if it exists AND we set --overwrite
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))        
    
    if not os.path.exists(output_file):
        # Only run if the file doesn't exist.
        logger.debug("Generating PDF for page {}".format(str(page)))
        op = ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite', '-sOutputFile={}'.format(output_file),
        '-dFirstPage={}'.format(str(page)), '-dLastPage={}'.format(str(page)), pdf ]
        if not doSystemCall(op):
            quit()
    return output_file

'''Which way to get OCR.

Keyword arguments
tiffFile -- Tiff file to process from
hocrFile -- Hocr file to extract from
outDir -- Directory to write OCR file to.
'''
def getOcr(tiffFile, hocrFile, outDir):
    if hocrFile is not None and os.path.exists(hocrFile) and os.path.isfile(hocrFile):
        getOcrFromHocr(hocrFile, outDir)
    elif tiffFile is not None and os.path.exists(tiffFile) and os.path.isfile(tiffFile):
        processOCR(tiffFile, outDir)
    else:
        logger.error("No tiff file or HOCR file to process for OCR")

'''Extract OCR from the Hocr data

Keyword arguments
hocrFile -- The HOCR file
outDir -- Directory to write OCR file to.
'''
def getOcrFromHocr(hocrFile, outDir):
    output_file = os.path.join(outDir, 'OCR.txt')
    if os.path.exists(output_file) and os.path.isfile(output_file) and options['overwrite']:
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))    
    if not os.path.exists(output_file):
        logger.debug("Generating OCR.")     
        data = ''
        with open(hocrFile, 'r') as fpr:
            data += fpr.read()
        data = html.unescape(blanklines.sub('', htmlmatch.sub('\1', data)))
        with open(output_file, 'w') as fpw:            
            fpw.write(data)        
        
        
'''Get the OCR from a Tiff file.

Keyword arguments
tiffFile -- The TIFF image
outDir -- The output directory'''
def processOCR(tiffFile, outDir):
    output_file = os.path.join(outDir, 'OCR');
    if os.path.exists(output_file) and os.path.isfile(output_file) and options['overwrite']:
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))
    if not os.path.exists(output_file):
        logger.debug("Generating OCR.")
        op = ['tesseract', tiffFile, output_file, '-l', options['language']]
        if not doSystemCall(op):
            quit()
        
'''Get the HOCR from a Tiff file.

Keyword arguments
tiffFile -- The TIFF image
outDir -- The output directory'''
def getHocr(tiffFile, outDir):
    output_stub = os.path.join(outDir, 'HOCR');
    output_file = output_stub + '.hocr'
    if os.path.exists(output_file) and os.path.isfile(output_file) and options['overwrite']:
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))
    if not os.path.exists(output_file):
        logger.debug("Generating HOCR.")
        op = ['tesseract', tiffFile, output_stub, '-l', options['language'], 'hocr']
        if not doSystemCall(op):
            quit()
    return output_file

'''Execute an external system call

Keyword arguments
ops -- a list of the executable and any arguments.
'''
def doSystemCall(ops):
    try:
        process = subprocess.Popen(ops, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            outs, errs = process.communicate(timeout=60)
            if not process.returncode == 0:
                logger.error("Error executing command: \n{}\nOutput: {}\nError: {}".format(' '.join(ops), outs, errs))
                return False
        except TimeoutError:
            logger.error("Error executing command: \n{}\nMessage: {}\nOutput: {}\nSTDOUT: ".format(e.cmd, e.stderr, e.output, e.stdout))
            return False
    except subprocess.CalledProcessError as e:
        logger.error("Error executing command: \n{}\nMessage: {}\nOutput: {}\nSTDOUT: ".format(e.cmd, e.stderr, e.output, e.stdout))
        return False
    return True


'''Count the number of pages in a PDF

Keyword arguments
pdf -- the full path to the PDF file
'''
def countPages(pdf):
    count = 0
    with open(pdf, 'rb') as fp:
        count += len(rxcountpages.findall(fp.read()))
    if count == 0:
        pdfRead = PyPDF2.PdfFileReader(pdf)
        count = pdfRead.getNumPages()
        pdfRead = None
    return count
    

'''Act on all PDFs in a directory, not recursing down.

Keyword arguments
theDir -- The full path to the directory to operate on
'''   
def parseDir(theDir):
    files = [f for f in os.listdir(theDir) if re.search('.*\.pdf$', f)]
    #for (dirpath, dirnames, filenames) in os.walk(theDir):
    #   for pdf in [m.group(0) for l in filenames for m in [regex.search(l)] if m]:
    for f in files: 
        processPdf(os.path.join(theDir, f))

'''Do setup functions

Keyword arguments
args -- the ArgumentParser object
'''
def setUp(args):
    global options
    setupLog()
    try:
        for prog in required_programs:
            subprocess.run([prog.get('exec'), prog.get('check_var')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError as e:
        print("A required program could not be found: {}".format(e.strerror.split(':')[1]))
        quit()
    options['overwrite'] = args.overwrite
    if len(args.password) > 0:
        options['password'] = args.password
    if args.language is not None:
        options['language'] = args.language

'''Setup logging'''
def setupLog():
    global logger
    logger = logging.getLogger('pdf2book')
    logger.propogate = False
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'pdf2log.log'), 'w', 'utf-8')
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    

'''Format seconds '''
def formatTime(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s)
    
    
'''The main body of code'''
def main():    
    start_time = time.perf_counter()
    
    parser = argparse.ArgumentParser(description='Turn a PDF or set of PDFs into properly formatted directories for Islandora Book Batch.')
    parser.add_argument('files', help="A PDF file or directory of PDFs to process.")
    parser.add_argument('--password', dest="password", default='', help='Password to use when parsing the PDFs.')
    parser.add_argument('--overwrite', dest="overwrite", action='store_true', default=False, help='Overwrite any existing Tiff/PDF/OCR/Hocr files with new copies.')
    parser.add_argument('--language', dest="language", help="Language of the source material, used for OCRing. Defaults to eng.")
    args = parser.parse_args()

    if not args.files[0] == '/':
        # Relative filepath
        args.files = os.path.join(os.getcwd(), args.files)
        
    if os.path.isfile(args.files) and os.path.splitext(args.files)[1] == '.pdf':
        setUp(args)
        processPdf(args.files)
    elif os.path.isdir(args.files):
        setUp(args)
        parseDir(args.files)
    else:
        parser.error("{} could not be resolved to a directory or a PDF file".format(args.files))
    
    total_time = time.perf_counter() - start_time
    print("Finished in {}".format(formatTime(total_time)))
        
if __name__ == '__main__':
    main()
    quit()
