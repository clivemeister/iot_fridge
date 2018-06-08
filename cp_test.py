"""Test harness: when run as main, starts web server and kicks off background thread that reads sensors every
few seconds, writing to database.  You can do a http GET to retrieve the last few sensor readings from the
database as JSON.

"""
import json
import random
import string
import logging
import os

import cherrypy

from sensor import TemperatureSensor
from sensorReading import SensorReading
from sensorStore import SensorStore


@cherrypy.expose
class JSONGeneratorWebService(object):

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_out()
    def GET(self,n=10,sensor_name="*"):
        store = SensorStore()
        if sensor_name == "*":
            reading_list = store.get_readings(count=n)
        else:
            reading_list = store.get_readings_for_sensor(sensor_name,count=n)
        store.close()

        cherrypy.log("In GET: read back last {} readings from database for {}".format(n,sensor_name))
        results = dict()
        if sensor_name =="*" :
            results['label'] = "All sensor readings"
        else:
            results['label'] = sensor_name
        results['data'] = [[int(1000 * r.get_timestamp().timestamp()), r.get_value()] for r in reading_list]

        return results

    def POST(self, length=8):
        some_string = ''.join(random.sample(string.hexdigits, int(length)))
        cherrypy.session['mystring'] = some_string
        return some_string

    def PUT(self, another_string):
        cherrypy.session['mystring'] = another_string

    def DELETE(self):
        cherrypy.session.pop('mystring', None)

@cherrypy.expose
class Root(object): pass

def read_and_store_sensors():
    logging.info("reading the sensors and writing to the database")

    store = SensorStore()

    # TODO switch to real sensors
    sensor_list = [TemperatureSensor("thermometer 1"), TemperatureSensor("thermometer 2")]

    # Read the sensors
    sensor_readings = []
    for s in sensor_list:
        sensor_readings.append(s.get_reading())

    # Write the results to the local db
    for r in sensor_readings:
        store.add_reading(sensor_name=r.get_name(), when=r.get_timestamp(),
                          reading_type=r.get_type(), value=r.get_value())

    cherrypy.log("Completed sensor readings")

    store.close()

if __name__ == '__main__':
    # Kick off the background process that reads the sensor values into the database
    pr = cherrypy.process.plugins.BackgroundTask(5,read_and_store_sensors)
    pr.start()

    # Set up configs for the different application classes that we run
    json_conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json'),('Access-Control-Allow-Origin', '*')],
        }
    }

    PATH = os.path.abspath(os.path.dirname(__file__))
    html_conf = {
        '/': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': PATH,
            'tools.staticdir.index': 'index.html'

        }
    }

    # Attach the JSON web service applications to the right places
    cherrypy.tree.mount(JSONGeneratorWebService(), '/json', json_conf)
    # Attach the file serving application
    cherrypy.tree.mount(Root(), '/', html_conf)

    # Boot up the web server
    cherrypy.engine.start()
    cherrypy.engine.block()