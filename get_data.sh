#!/bin/bash

for ((i=0; i<100; i++))
do
#### googlenet ####
#	./use_archive_sub.py ./capston/aaa.tar.gz image.JPG
#### alexnet ####
	./use_archive_sub.py ./alexnet/20160819-001812-17d5_epoch_97.0.tar.gz image.JPG --nogpu
#### VGG ####
#	./use_archive_sub.py ./vggnet/20161031-154522-56aa_epoch_29.0.tar.gz image.JPG

done
