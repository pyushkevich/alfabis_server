#!/usr/bin/env python
import web,sys

# Create the web app
urls = (r'/', 'index')
app = web.application(urls, globals())

# Redirect to https
class index:
  def GET(self):
    raise web.seeother('https://dss.itksnap.org')


if __name__ == '__main__' :
  app.run()
