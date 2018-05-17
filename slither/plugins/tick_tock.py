import time

def tick_tock(broker, path, args):
    """Publish the current time in epoch to the time.tick
    topic every second and the time.tock topic every minute
    using broker.
    """
    while True:
        t = time.time()
        broker.pub("time.tick", t)
        if int(t)%60 == 0:
            broker.pub("time.tock", int(t))
        time.sleep(1)
#       The below line has similar drift but higher CPU usage
#       a better idea Would appreciated.
#        time.sleep(1 - (time.time()-t))
