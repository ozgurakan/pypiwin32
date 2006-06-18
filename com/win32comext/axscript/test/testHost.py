import string, sys
from win32com.axscript.server.error import Exception
from win32com.axscript import axscript
from win32com.axscript.server import axsite
import pythoncom
from win32com.server import util, connect
import win32com.server.policy

import unittest
import win32com.test.util

verbose = "-v" in sys.argv

class MySite(axsite.AXSite):
  def __init__(self, *args):
    self.seen_exception = 0
    axsite.AXSite.__init__(self, *args)

  def OnScriptError(self, error):
    exc = error.GetExceptionInfo()
    context, line, char = error.GetSourcePosition()
    self.seen_exception = 1
    if not verbose:
      return
    print " >Exception:", exc[1]
    try:
      st = error.GetSourceLineText()
    except pythoncom.com_error:
      st = None
    if st is None: st = ""
    text = st + "\n" + (" " * (char-1)) + "^" + "\n" + exc[2]
    for line in string.split(text,"\n"):
      print "  >" + line

class MyCollection(util.Collection):
	def _NewEnum(self):
		return util.Collection._NewEnum(self)

class Test:
  _public_methods_ = [ 'echo', 'fail' ]
  _public_attrs_ = ['collection']
  def __init__(self):
    self.verbose = verbose
    self.collection = util.wrap( MyCollection( [1,'Two',3] ))
    self.last = ""
    self.fail_called = 0
#    self._connect_server_ = TestConnectServer(self)

  def echo(self, *args):
    self.last = string.join(map(str, args))
    if self.verbose:
      for arg in args:
        print arg,
      print

  def fail(self, *args):
    print "**** fail() called ***"
    for arg in args:
      print arg,
    print
    self.fail_called = 1
#    self._connect_server_.Broadcast(last)


#### Connections currently wont work, as there is no way for the engine to
#### know what events we support.  We need typeinfo support.

IID_ITestEvents = pythoncom.MakeIID("{8EB72F90-0D44-11d1-9C4B-00AA00125A98}")

class TestConnectServer(connect.ConnectableServer):
	_connect_interfaces_ = [IID_ITestEvents]
	# The single public method that the client can call on us
	# (ie, as a normal COM server, this exposes just this single method.
	def __init__(self, object):
		self.object = object
		
	def Broadcast(self,arg):
		# Simply broadcast a notification.
		self._BroadcastNotify(self.NotifyDoneIt, (arg,))

	def NotifyDoneIt(self, interface, arg):
		interface.Invoke(1000, 0, pythoncom.DISPATCH_METHOD, 1, arg)

VBScript = """\
prop = "Property Value"

sub hello(arg1)
   test.echo arg1
end sub
  
sub testcollection
   if test.collection.Item(0) <> 1 then
     test.fail("Index 0 was wrong")
   end if
   if test.collection.Item(1) <> "Two" then
     test.fail("Index 1 was wrong")
   end if
   if test.collection.Item(2) <> 3 then
     test.fail("Index 2 was wrong")
   end if
   num = 0
   for each item in test.collection
     num = num + 1
   next
   if num <> 3 then
     test.fail("Collection didn't have 3 items")
   end if
end sub
"""
PyScript = u"""\
# A unicode \xa9omment.
prop = "Property Value"
def hello(arg1):
   test.echo(arg1)
   
def testcollection():
#   test.collection[1] = "New one"
   got = []
   for item in test.collection:
     got.append(item)
   if got != [1, "Two", 3]:
     test.fail("Didn't get the collection")
   pass
"""

ErrScript = """\
bad code for everyone!
"""

state_map = {
	axscript.SCRIPTSTATE_UNINITIALIZED: "SCRIPTSTATE_UNINITIALIZED",
	axscript.SCRIPTSTATE_INITIALIZED: "SCRIPTSTATE_INITIALIZED",
	axscript.SCRIPTSTATE_STARTED: "SCRIPTSTATE_STARTED",
	axscript.SCRIPTSTATE_CONNECTED: "SCRIPTSTATE_CONNECTED",
	axscript.SCRIPTSTATE_DISCONNECTED: "SCRIPTSTATE_DISCONNECTED",
	axscript.SCRIPTSTATE_CLOSED: "SCRIPTSTATE_CLOSED",
}

def _CheckEngineState(engine, name, state):
  got = engine.engine.eScript.GetScriptState()
  if got != state:
    got_name = state_map.get(got, str(got))
    state_name = state_map.get(state, str(state))
    raise RuntimeError, "Warning - engine %s has state %s, but expected %s" % (name, got_name, state_name)

class EngineTester(win32com.test.util.TestCase):
  def _TestEngine(self, engineName, code, bShouldWork = 1):
    echoer = Test()
    model = {
      'test' : util.wrap(echoer),
      }
    try:
      try:
        site = MySite(model)
        engine = site._AddEngine(engineName)
        _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_INITIALIZED)
        engine.AddCode(code)
        engine.Start()
        _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_STARTED)
      finally:
        if bShouldWork:
          self.failUnless(not site.seen_exception, "Script site should not have seen an exception")
        else:
          self.failUnless(site.seen_exception, "Script site should have seen an exception")
      self.failUnless(not echoer.fail_called, "Fail should not have been called")
      # Now call into the scripts IDispatch
      from win32com.client.dynamic import Dispatch
      ob = Dispatch(engine.GetScriptDispatch())
      ob.hello("Goober")
      self.assertEqual(echoer.last, "Goober")
  
      self.assertEqual(str(ob.prop), "Property Value")
      ob.testcollection()
      self.failUnless(not echoer.fail_called, "Fail should not have been called")
  
      # Now make sure my engines can evaluate stuff.
      result = engine.eParse.ParseScriptText("1+1", None, None, None, 0, 0, axscript.SCRIPTTEXT_ISEXPRESSION)
      self.assertEqual(result, 2)
      # re-initialize to make sure it transitions back to initialized again.
      engine.SetScriptState(axscript.SCRIPTSTATE_INITIALIZED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_INITIALIZED)
      engine.Start()
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_STARTED)
      
      # Transition back to initialized, then through connected too.
      engine.SetScriptState(axscript.SCRIPTSTATE_INITIALIZED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_INITIALIZED)
      engine.SetScriptState(axscript.SCRIPTSTATE_CONNECTED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_CONNECTED)
      engine.SetScriptState(axscript.SCRIPTSTATE_INITIALIZED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_INITIALIZED)
    
      engine.SetScriptState(axscript.SCRIPTSTATE_CONNECTED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_CONNECTED)
      engine.SetScriptState(axscript.SCRIPTSTATE_DISCONNECTED)
      _CheckEngineState(site, engineName, axscript.SCRIPTSTATE_DISCONNECTED)
    finally:
      engine.Close()
      engine = None
      site = None

  def testVB(self):
    self._TestEngine("VBScript", VBScript)
  def testPython(self):
    self._TestEngine("Python", PyScript)
  def testVBExceptions(self):
    self.assertRaises(pythoncom.com_error,
                      self._TestEngine, "VBScript", ErrScript, 0)
  def testPythonExceptions(self):
    self.assertRaises(pythoncom.com_error,
                      self._TestEngine, "Python", ErrScript, 0)

if __name__ == '__main__':
  unittest.main()
