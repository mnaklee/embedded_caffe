#!/usr/bin/env python
# Copyright (c) 2015, NVIDIA CORPORATION.  All rights reserved.

"""
Classify an image using a model archive file
"""

import argparse
import os, re, sys
import time
import zipfile
import tarfile
import tempfile
import json
import math


import PIL.Image
from PIL import Image
import numpy as np
import scipy.misc
from google.protobuf import text_format
import wt310

os.environ['GLOG_minloglevel'] = '2' # Suppress most caffe output
import caffe
from caffe.proto import caffe_pb2

net=0
transformer = 0
caffemodel = 0
deploy_file = 0
mean_file = 0
labels_file = 0
#predicArr[10][10] = 0

#from exam import classify

def unzip_archive(archive):
    """
    Unzips an archive into a temporary directory
    Returns a link to that directory

    Arguments:
    archive -- the path to an archive file
    """
    tmpdir = os.path.join(tempfile.gettempdir(),
            os.path.basename(archive))
    assert tmpdir != archive # That wouldn't work out

    if os.path.exists(tmpdir):
        # files are already extracted
        pass
    else:
        if tarfile.is_tarfile(archive):
            print 'Extracting tarfile ...'
            with tarfile.open(archive) as tf:
                tf.extractall(path=tmpdir)
        elif zipfile.is_zipfile(archive):
            print 'Extracting zipfile ...'
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(path=tmpdir)
        else:
            raise ValueError('Unknown file type for %s' % os.path.basename(archive))
    return tmpdir

#############################################################################################
def get_net(caffemodel, deploy_file, use_gpu=True):
    """
    Returns an instance of caffe.Net

    Arguments:
    caffemodel -- path to a .caffemodel file
    deploy_file -- path to a .prototxt file

    Keyword arguments:
    use_gpu -- if True, use the GPU for inference
    """

    if use_gpu:
        caffe.set_mode_gpu()

    # load a new model
    return caffe.Net(deploy_file, caffemodel, caffe.TEST)
    #return caffe.Net('./model/20160418-093723-c2f4_epoch_57.0.tar.gz','./model/20160418-093723-c2f4_epoch_57.0.tar.gz',caffe.TEST)

def get_transformer(deploy_file, mean_file=None):
    """
    Returns an instance of caffe.io.Transformer

    Arguments:
    deploy_file -- path to a .prototxt file

    Keyword arguments:
    mean_file -- path to a .binaryproto file (optional)
    """
    network = caffe_pb2.NetParameter()
    with open(deploy_file) as infile:
        text_format.Merge(infile.read(), network)

    if network.input_shape:
        dims = network.input_shape[0].dim
    else:
        dims = network.input_dim[:4]

    t = caffe.io.Transformer(
            inputs = {'data': dims}
            )
    t.set_transpose('data', (2,0,1)) # transpose to (channels, height, width)

    # color images
    if dims[1] == 3:
        # channel swap
        t.set_channel_swap('data', (2,1,0))

    if mean_file:
        # set mean pixel
        with open(mean_file,'rb') as infile:
            blob = caffe_pb2.BlobProto()
            blob.MergeFromString(infile.read())
            if blob.HasField('shape'):
                blob_dims = blob.shape
                assert len(blob_dims) == 4, 'Shape should have 4 dimensions - shape is "%s"' % blob.shape
            elif blob.HasField('num') and blob.HasField('channels') and \
                    blob.HasField('height') and blob.HasField('width'):
                blob_dims = (blob.num, blob.channels, blob.height, blob.width)
            else:
                raise ValueError('blob does not provide shape or 4d dimensions')
            pixel = np.reshape(blob.data, blob_dims[1:]).mean(1).mean(1)
            t.set_mean('data', pixel)

    return t

def load_image(path, height, width, mode='RGB'):
    """
    Load an image from disk

    Returns an np.ndarray (channels x width x height)

    Arguments:
    path -- path to an image on disk
    width -- resize dimension
    height -- resize dimension

    Keyword arguments:
    mode -- the PIL mode that the image should be converted to
        (RGB for color or L for grayscale)
    """
    image = PIL.Image.open(path)
    image = image.convert(mode)
    image = np.array(image)
    # squash
    image = scipy.misc.imresize(image, (height, width), 'bilinear')
    return image

def forward_pass(images, net, transformer, batch_size=50):
    """
    Returns scores for each image as an np.ndarray (nImages x nClasses)

    Arguments:
    images -- a list of np.ndarrays
    net -- a caffe.Net
    transformer -- a caffe.io.Transformer

    Keyword arguments:
    batch_size -- how many images can be processed at once
        (a high value may result in out-of-memory errors)
    """
    caffe_images = []
    for image in images:
        if image.ndim == 2:
            caffe_images.append(image[:,:,np.newaxis])
        else:
            caffe_images.append(image)

    caffe_images = np.array(caffe_images)

    dims = transformer.inputs['data'][1:]
	#batch_size = 100
    
    print "NONONO%s"%batch_size
    
    scores = None
    for chunk in [caffe_images[x:x+batch_size] for x in xrange(0, len(caffe_images), batch_size)]:
        new_shape = (len(chunk),) + tuple(dims)
        if net.blobs['data'].data.shape != new_shape:
            net.blobs['data'].reshape(*new_shape)
        for index, image in enumerate(chunk):
            image_data = transformer.preprocess('data', image)
            net.blobs['data'].data[index] = image_data
        output = net.forward()[net.outputs[-1]]
        #print output['prob']
        if scores is None:
            scores = np.copy(output)
			#print 'KYU'
            #print '%s' % scores
        else:
            scores = np.vstack((scores, output))
            print 'HEO'
            #print '%s' % scores
        print 'Processed %s/%s images ...' % (len(scores), len(caffe_images))

    return scores

def read_labels(labels_file):
    """
    Returns a list of strings

    Arguments:
    labels_file -- path to a .txt file
    """
    if not labels_file:
        print 'WARNING: No labels file provided. Results will be difficult to interpret.'
        return None

    labels = []
    with open(labels_file) as infile:
        for line in infile:
            label = line.strip()
            if label:
                labels.append(label)
    assert len(labels), 'No labels found'
    return labels

##################################
def showIMG(image_files):
    #filename = "good.jpg";
    #img = Image.open("good.jpg");
    img = Image.open(image_files)
    print img
    img.show();
    #del img
############################################################################################3

    

###################################after Here need to Thread############################
def classify(caffemodel, deploy_file, image_files,mean_file, labels_file, use_gpu,net,transformer):
	
    _, channels, height, width = transformer.inputs['data']
    
    if channels == 3:
        mode = 'RGB'
    elif channels == 1:
        mode = 'L'
    else:
        raise ValueError('Invalid number for channels: %s' % channels)
        
    imagetime = time.time()
    images = [load_image(image_file, height, width, mode) for image_file in image_files]
    #showIMG(image_files)
    
    print 'images lead time %s' %(time.time() - imagetime)

    labeltime = time.time()
    labels = read_labels(labels_file)
    print 'label lead time %s' %(time.time() - labeltime)

    # Classify the image
    classify_start_time = time.time()
    scores = forward_pass(images, net, transformer)
    print 'Classification took %s seconds.' % (time.time() - classify_start_time,)
    print scores

    ### Process the results

    tempaaa = time.time()

    indices = (-scores).argsort()[:, :25] # take top 5 results
    classifications = []
    for image_index, index_list in enumerate(indices):
        result = []
        for i in index_list:
            # 'i' is a category in labels and also an index into scores
            if labels is None:
                label = 'Class #%s' % i
            else:
                label = labels[i]
            result.append((label, round(100.0*scores[image_index, i],4)))
        classifications.append(result)

    print
    print 'after labeling %s ' % (time.time() - tempaaa,)
    print

    tempbbb = time.time()
    idx = 0
    #global predicArr[10][10]
    predicArr = [[0 for col in range(30)] for row in range(30)]

    for index, classification in enumerate(classifications):
		
        print '{:-^80}'.format(' Prediction for %s ' % image_files[index])
        for label, confidence in classification:
            print '{:9.4%} - "{}"'.format(confidence/100.0, label)
            predicArr[idx][0] = confidence/100.0
            predicArr[idx][1] = label      
            idx=idx+1
        print

    print 'after prediction %s' % (time.time() - tempbbb)
    print
    
    return predicArr

#############################################################################################
    

def preprocessFunc(archive, image_files, use_gpu=True):
    """
    """
    startTime = time.time()

    tmpdir = unzip_archive(archive)
    global caffemodel 
    caffemodel = None
    global deploy_file 
    deploy_file = None
    global mean_file 
    mean_file = None
    global labels_file 
    labels_file = None
    
    for filename in os.listdir(tmpdir):
        full_path = os.path.join(tmpdir, filename)
        if filename.endswith('.caffemodel'):
            caffemodel = full_path
        elif filename == 'deploy.prototxt':
            deploy_file = full_path
        elif filename.endswith('.binaryproto'):
            mean_file = full_path
        elif filename == 'labels.txt':
            labels_file = full_path
        else:
            print 'Unknown file:', filename

    assert caffemodel is not None, 'Caffe model file not found'
    assert deploy_file is not None, 'Deploy file not found'

    
    startTime = time.time()

    # Load the model and images
    global net
    net = get_net(caffemodel, deploy_file, use_gpu) 
    
    print 'get_net lead time (read model instance) : %s' % (time.time() - startTime)

    get_net_time = time.time()

    global transformer 
    transformer = get_transformer(deploy_file, mean_file)

    print 'after transfomer(get tranform) : %s' %(time.time() - get_net_time)


if __name__ == '__main__':
    script_start_time = time.time()

    parser = argparse.ArgumentParser(description='Classification example using an archive - DIGITS')

    ### Positional arguments

    parser.add_argument('archive',  help='Path to a DIGITS model archive')
    parser.add_argument('image',    help='Path to an image')

    ### Optional arguments

    parser.add_argument('--nogpu',action='store_true',help="Don't use the GPU")

    args = vars(parser.parse_args())

    image_files = [args['image']]
    
    print 'ssssssssssssss %s' % image_files
  
    #print 'before insert classify time %s' % (time.time() - script_start_time,)


	############################preprocess###############################
    
    preprocessFunc(args['archive'], image_files, not args['nogpu'])
    
    #####################################################################
    
    my_energy = wt310.wt310_reader()
    my_energy.open()

    s = my_energy.start() 
    startTime = time.time()
    
    answerArr = [[0 for col in range(6)] for row in range(6)]
    
    answerArr = classify(caffemodel, deploy_file, image_files,mean_file, labels_file, not args['nogpu'],net,transformer)
    
    
    for j in range(0,5):
	print '%s %s' %(answerArr[j][0]*100 , answerArr[j][1])
    c_time = time.time()-startTime
    my_energy.stop()
    s=my_energy.sample()
    ev = s['J'] #energy
    pv = s['P'] #power
    str = '%.2lf %.2lf' % (ev,pv)
    print '###############################################################################'
    print 'classification lead time : %s  #####################################' % (time.time() - startTime)
#    print >> open('clf_default_alexnet.txt', 'a'), '%s %s' % (c_time, str)
#    print >> open('clf_zerocpy_googlenet.txt', 'a'), '%s %s' % (c_time, str)
    print >> open('clf_nogpu_alexnet.txt', 'a'), '%s %s' % (c_time, str)
    print '###############################################################################'
    
    
    print 'TotalTime %s seconds.' % (time.time() - script_start_time,)

