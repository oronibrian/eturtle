from decimal import Decimal
import logging
from datetime import datetime, timedelta
import urllib
import urllib2
from django.core.cache import cache
from server.dispatch.models import Courier, Package, Dispatch
from math import sqrt

def get_google_token():
    auth_token = cache.get('google_auth_token',None)
    if auth_token:
        return auth_token
    
    data = urllib.urlencode({
                    'Email':'ernestturtle@gmail.com',
                    'Passwd':'turtleadmin',
                    'accountType':'HOSTED_OR_GOOGLE',
                    'source':'Google-cURL-Example',
                    'service':'ac2dm',
            })
    request = urllib2.Request(
            url='https://www.google.com/accounts/ClientLogin',
            data = data)

    response = urllib2.urlopen(request)
    code = response.getcode()
    if response.getcode()==200:
        s = response.read()
        auth_token = s.split('Auth=')[1]
        auth_token = auth_token.strip()
        cache.set('google_auth_token', auth_token)
        return auth_token

    raise Exception('Google auth token error:%s' % code)

def push(courier, message):
    registration_id = courier.c2dmkey
    token = get_google_token()

    data = urllib.urlencode({
                    'registration_id':registration_id,
                    'data.message':message,
                    'collapse_key':1
            })

    request = urllib2.Request(
            url='https://android.apis.google.com/c2dm/send',
            data = data)
    request.add_header("Authorization","GoogleLogin auth=%s" % token)
    response = urllib2.urlopen(request)

    code = response.getcode()
    body = response.read()

    logger = logging.getLogger('c2dm_logger')
    logger.info("%s | %s | %s | %s" % (courier, datetime.now().isoformat(), code, body.strip()))
    return body

def run_dispatcher(timeout=120):
    logger = logging.getLogger('dispatch_logger')

    #check and resolve timed out Dispatches
    tod = Dispatch.objects.filter(
                            state=Dispatch.STATE_PENDING,
                            date_created__lte=datetime.now()-timedelta(seconds=timeout))

    logger.info("Timed out: %d packages" % tod.count())

    Package.objects.filter(dispatch=tod).update(state=Package.STATE_NEW)
    for c in Courier.objects.filter(dispatch=tod):
        #for every timed out courier send a c2dm and update states
        push(c,"TIMEOUT")
        c.state=Courier.STATE_IDLE
        c.save()
    
    tod.update(state=Dispatch.STATE_TIMED_OUT)
    # ---

    packages = Package.objects.filter(state=Package.STATE_NEW)
    couriers = Courier.objects.filter(state=Courier.STATE_STANDING_BY)

    num_packages = packages.count()
    num_couriers = couriers.count()

    assignments=[]

    if num_packages and num_couriers:
        for p in packages:
            """
            Second chance algorithm:
            If a courier rejects he will not be dispatched the same package again.
            If all couriers reject the package, the initial courier will recieve it again.
            """

            #Querying standing by couriers who have never recieved a dispatch for this package
            #The only way they can have one in this scenario is if they rejected it
            couriers = Courier.objects.filter(state=Courier.STATE_STANDING_BY).exclude(dispatch__package=p)
            nearest_courier = None
            min_d=Decimal('infinity')
            if couriers.count():
                for c in couriers:

                    try:
                        d=sqrt((abs(float(p.src_lat)-float(c.lat)))**2 + (abs(float(p.src_lng)-float(c.lng)))**2)
                        if d<min_d:
                            min_d = d
                            nearest_courier =c
                    except ValueError:
                        print "ValueError for package %s" % p
                        continue

                
            
            else:
                couriers = Courier.objects.filter(state=Courier.STATE_STANDING_BY)
                if not couriers.count():
                    continue
                #there were no couriers who have never rejected, now we retry with all couriers
                for c in couriers:

                    try:
                        d=sqrt((abs(float(p.src_lat)-float(c.lat)))**2 + (abs(float(p.src_lng)-float(c.lng)))**2)
                        if d<min_d:
                            min_d = d
                            nearest_courier =c
                    except ValueError:
                        print "ValueError for package %s" % p
                        continue

            #dispatch the packege to the nearest_courier:
            nearest_courier.state=Courier.STATE_PENDING
            nearest_courier.save()
            p.state=Package.STATE_PENDING
            p.save()
            Dispatch(courier=nearest_courier,package=p).save()
    
            #send push notification to courier:
            push(nearest_courier,p.serialize())

            assignments.append((nearest_courier,p))
    
    a="\n".join(["%s : %s" % (a[0],a[1]) for a in assignments]) or "No new assignments."
    logger.info("Packages:%d, Couriers:%d\n%s\n%s\n" % (num_packages,num_couriers,a,datetime.now().isoformat()))
