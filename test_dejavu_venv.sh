#####################################
### Dejavu example testing script ###
#####################################

###########
# Clear out previous results
rm -rf ./results ./temp_audio

###########
# Fingerprint files of extension mp3 in the ./mp3 folder
./venv/bin/python dejavu.py -f ./wav/ wav

##########
# Run a test suite on the ./mp3 folder by extracting 1, 2, 3, 4, and 5 
# second clips sampled randomly from within each song 8 seconds 
# away from start or end, sampling with random seed = 42, and finally 
# store results in ./results and log to dejavu-test.log
./venv/bin/python run_tests.py \
	--sec 5 \
	--temp ./temp_audio \
	--log-file ./results/dejavu-test.log \
	--padding 8 \
	--seed 42 \
	--results ./results \
  --python ./venv/bin/python \
	./wav

