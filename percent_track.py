import numpy as np
import cv2
import sys

# hardcoded size of zero template...
WIDTH = 35
HEIGHT = 39
DIFF_METHOD = 'cv2.TM_CCOEFF_NORMED'
# include a buffer for candidate size, augment each side by 5 pixels to account for shakiness
BUFFER_SIZE = 8

def load_resources():
    # grab resources and put them into number_templates
    number_templates = []
    for i in range(0,10):
        number_templates.append(cv2.imread('smash_resources_v2/' + str(i) + '.png', 1))
    return number_templates

def read_and_preprocess_frame(cap, source):
    # preprocess frame depending on source...
    # assuming frame is in top 480 x 640 rectangle, chop just that
    ret, frame = cap.read()
    if ret == True:
        if source == 'mangoFalco.mp4':
            frame = frame[0:479, 0:639]
        elif source == 'falconDitto.mp4':
            #its only 360 x 480
            frame = frame[0:359, 81:560]
            frame = cv2.resize(frame, (640, 480))
    return ret, frame

def find_zeros(frame, zero):
    #given frame and zero template, find top two matching locations using
    #cv2.matchTemplate
    diff = cv2.matchTemplate(frame, zero, eval(DIFF_METHOD))
    cv2.imshow('diff', diff)
    cv2.waitKey(0)
    # flatten out the diff array so we can sort it
    diff2 = np.reshape(diff, diff.shape[0]*diff.shape[1])
    # sort in reverse order
    sort = np.argsort(-diff2)
    print "sort: " + str(sort)
    ret = []
    (y1, x1) = (np.unravel_index(sort[0], diff.shape)) #best match
    ret.append((x1, y1))
    (y2, x2) = (np.unravel_index(sort[1], diff.shape)) #second best match
    ret.append((x2, y2))
    print "ret: " + str(ret)
    return ret

def draw_around_percents(frame, extended_locations_found):
    for top_left in extended_locations_found:
        print "top left: " + str(top_left)
        bottom_right = (top_left[0] + WIDTH + (2 * BUFFER_SIZE), top_left[1] + HEIGHT + (2 * BUFFER_SIZE))
        cv2.rectangle(frame, top_left, bottom_right, 255, 2)
    cv2.imshow('frame', frame)
    cv2.waitKey(0)    

def compare_with_previous(img1, img2, locations_found):
    # compare img1 with img2 and see if anything changed significantly in locations_found
    # if diff falls below diff_threshold, then percentage has changed
    # don't necessarily need to include buffer for this
    diff_threshold = 0.9
    for location in locations_found:
        # location[0] is horizontal, location[1] is vertical 
        # but you need to index into image vertically then horizontally
        percent_1 = img1[location[1]:location[1] + HEIGHT, location[0]:location[0] + WIDTH]
        percent_2 = img2[location[1]:location[1] + HEIGHT, location[0]:location[0] + WIDTH]
        diff = cv2.matchTemplate(percent_1, percent_2, eval(DIFF_METHOD))[0][0]
        # print "diff: " + str(diff)
        if diff < diff_threshold:
            return False
    return True

def match_to_number(candidate, number_templates):
    # try to match candidate to each image in number_templates
    # candidate should be bigger than number to allow room for moving around
    prev_val = float("-inf")
    max_idx = -1
    max_val = prev_val
    for index, number in enumerate(number_templates):
        #cv2.imshow('compare1', candidate)
        #cv2.imshow('compare2', number)
        cur_diff = cv2.matchTemplate(candidate, number, eval(DIFF_METHOD))
        _, cur_val, _, _ = cv2.minMaxLoc(cur_diff)
        #print "cur_diff: " + str(cur_diff)
        #cv2.waitKey(0)
        if cur_val > max_val:
            max_val = cur_val
            max_idx = index
    # if there's something reasonably close, return that...
    if max_val > 0.7:
        return max_idx
    # otherwise return -1
    return -1

def extend_locations(locations):
    # for each 0 location found, find two boxes to right
    # then extend each box by buffer size
    DISTANCE = WIDTH - 3
    extended_locations = []
    buffered_locations = []
    for location in locations:
        extended_locations.append((location[0], location[1]))
        extended_locations.append((location[0] - DISTANCE, location[1]))
        extended_locations.append((location[0] - (2 * DISTANCE), location[1]))
    for location in extended_locations:
        buffered_locations.append((location[0] - BUFFER_SIZE, location[1] - BUFFER_SIZE))
    return buffered_locations, extended_locations    

def calculate_total_percent(ones, tens, hundreds):
    # calculate actual value from three digits...
    # return -1 if percentage does not make sense.
    if ones == -1:
        return -1
    total = ones;
    if hundreds != -1:
        total += hundreds * 100
    if tens != -1:
        total += tens * 10
    return total

def get_args(argv):
    if len(argv) < 2:
        print 'python percent_track.py <filename> <frames to skip>'
        sys.exit()

    file_name = sys.argv[1]

    # 1400 frames to start for falconDitto, 150 for mangoFalco
    if len(argv) < 3:
      frames_to_start = 0
    else:
      frames_to_start = int(sys.argv[2])

    return file_name, frames_to_start

def forward_video(video_data, frames_to_start):
    for i in range(1, frames_to_start):
        video_data['cap'].read()    
    video_data['ret'], video_data['frame'] = read_and_preprocess_frame(video_data['cap'], video_data['file_name'])

    return video_data

def init_video(argv):
    file_name, frames_to_start = get_args(argv) 
    cap = cv2.VideoCapture(file_name)

    video_data = {'cap': cap, 'file_name': file_name}

    video_data = forward_video(video_data, frames_to_start)

    return video_data

def main(argv = sys.argv):
    video_data = init_video(argv)

    # find where percentages are using template matching
    # load the zero template, use matchTemplate to find spots which are closest to it
    number_templates = load_resources()
    zero = number_templates[0]
    # locations_found is the places where we think the zeros are
    # its an list of x,y pairs
    locations_found = find_zeros(video_data['frame'], zero) 
    extended_locations_found, _ = extend_locations(locations_found)
    # draw a rectangle around each location, using hardcoded values of size of percents
    draw_around_percents(video_data['frame'], extended_locations_found)

    _, previous_frame = read_and_preprocess_frame(video_data['cap'], video_data['file_name'])
    prev_stability = False
    frames_elapsed = 0
    percent_series_1 = []
    percent_series_2 = []
    time_series = []
    while(video_data['cap'].isOpened()):
        video_data['ret'] ,video_data['frame'] = read_and_preprocess_frame(video_data['cap'], video_data['file_name'])
        frames_elapsed += 1
        if video_data['ret'] == True:
            cv2.imshow('frame', video_data['frame'])
            if not compare_with_previous(previous_frame, video_data['frame'], locations_found):
                # percentage will shake around, making it unstable
                # wait until stable again to look for difference between it and previous one
                cur_stability = False
            else: 
                cur_stability = True
            # if we've stabilized, check both percentages to see whats changed
            if cur_stability and not prev_stability:
                best_guesses = []
                for idx, location in enumerate(extended_locations_found):
                    candidate = video_data['frame'][location[1]:location[1] + HEIGHT + (2 * BUFFER_SIZE), location[0]:location[0] + WIDTH + (2 * BUFFER_SIZE)]
                    # cv2.imshow('candidate', candidate)
                    # cv2.waitKey(0)
                    best_guess = match_to_number(candidate, number_templates)
                    # print "location: " + str(idx)
                    # print "guessed percent: " + str(best_guess)
                    best_guesses.append(best_guess)
                percent_1 = calculate_total_percent(best_guesses[0], best_guesses[1], best_guesses[2])
                percent_2 = calculate_total_percent(best_guesses[3], best_guesses[4], best_guesses[5])
                time_elapsed = float(frames_elapsed)/60
                print "Location 1: " + str(percent_1) + " Location 2: " + str(percent_2) + " at frame " + str(frames_elapsed)
                percent_series_1.append(percent_1)
                percent_series_2.append(percent_2)
                time_series.append(frames_elapsed)
                #cv2.waitKey(0)
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break   
            prev_stability = cur_stability
        else:
            break
        previous_frame = video_data['frame']
    f = open(video_data['file_name'] + '_data.csv','w')
    for idx, time_stamp in enumerate(time_series):
        f.write(str(time_stamp) + ', ' + str(percent_series_1[idx]) + ', ' + str(percent_series_2[idx]) + '\n')
    f.close()
               
    cv2.destroyAllWindows()
    video_data['cap'].release()

if __name__ == "__main__":
    main()
