import re

#  #################################  General Functions #############
def in_post(req_post, find_this):
    '''
    Determines if the post contains one of the required elements to take action on
    :param req_post: request
    :param find_this: string part to look for
    :return: 0 if nothing found or int for the id contained in the post key
    '''
    for i in req_post:
        x = re.search(find_this, i)
        if x is not None:
            y = str(i)
            return get_object_id(y)
    return 0


def get_object_id(in_str):
    x = in_str.split('|')
    return int(x[1])
