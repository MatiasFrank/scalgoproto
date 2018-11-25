# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Test that everything works
"""

import subprocess, sys, tempfile
from typing import Callable 


failures=[]

def runValidate(schema:str, fail:bool=False)->bool:
	code = subprocess.call(["python3", "scalgoproto", "validate", schema])
	return fail == (code != 0)

def runCppSetup(schema: str, cpp: str) -> bool:
	subprocess.check_call(["python3", "scalgoproto", "cpp", schema, "tmp/test.hh"])
	subprocess.check_call(["g++", "-ggdb", "-std=c++17", "-Wall", "-Wextra", "-I", "tmp", "-I", "lib/cpp", cpp, "-o", "tmp/bin"])
	return True

def runCpp(name:str, bin:str) -> bool:
	subprocess.check_call(["tmp/bin", name, bin])
	return True

def runPySetup(schema: str) -> bool:
	subprocess.check_call(["python3", "scalgoproto", "py", schema, "tmp/base.py"])
	return True


def runPy(name:str, bin:str) -> bool:
	subprocess.check_call(["python3", "test/py.py", name, bin], env={'PYTHONPATH':"lib/python:tmp"})
	return True
	
def runTest(name:str, func: Callable[[],bool]) -> bool:
	l = 80 - len(name) - 4
	print("%s> %s <%s"%("="*(l//2 ), name, "="*(l - l//2)))
	ok = False
	try:
		ok = func()
	except:
		pass
	if ok:
		print("SUCCESS")
		return True
	else:
		print("FAILURE")
		failures.append(name)
		return False

def runNeg(name:str, base: str, bad:str, good:str) -> None:
	l = 80 - len(name) - 4
	print("%s> %s <%s"%("="*(l//2 ), name, "="*(l - l//2)))
	with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
		f.write(base%bad)
		f.flush()
		code = subprocess.call(["python3", "scalgoproto", "validate", f.name])
		if code == 0:
			print("FAILURE1")
			failures.append(name)
			return
	with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
		f.write(base%good)
		f.flush()
		code = subprocess.call(["python3", "scalgoproto", "validate", f.name])
		if code != 0:
			print("FAILURE2")
			failures.append(name)
			return
	print("SUCCESS")

def main():
	# Test names
	for (bad, good) in ( ("monkey", "Monkey"), ("Monkey_Cat", "MonkeyCat")):
		runNeg("bad table name %s"%bad, "table %s @8908828A {}", bad, good)
	for (bad, good) in ( ("Cat", "cat"), ("type", "myType"), ("cat_dog", "catDog")):
		runNeg("bad table member name %s"%bad, "table Monkey @8908828A {%s : UInt32}", bad, good)
	# Test table types
	for (bad, good) in ( ("Int", "Int32"), ("int32", "Int32"), ("bool", "Bool"), ("bytes", "Bytes"), ("text", "Text"), ("String", "Text")):
		runNeg("bad table member type %s"%bad, "table Monkey @8908828A {a: %s}", bad, good)

	# Test struct types
	for (bad, good) in ( ("optional UInt32", "UInt32"), ("UInt64 = 7", "UInt64"), ("list Bool", "Bool"), ("Bytes", "UInt8"), ("Text", "UInt16"), ("union {}", "Float32")):
		runNeg("bad struct member type %s"%bad, "struct Monkey {a: %s}", bad, good)

	# Test table id
	for (bad, good) in ( ("0x1234567", "@8908828A"), ("@8908828X", "@8908828A"), ("@8908828a", "@8908828A"), ("@8908828A78", "@8908828A"), ("", "@8908828A")):
		runNeg("table id %s"%bad, "table Monkey %s {}", bad, good)
	runNeg("table id inplace a", "table Monkey @8908828A {a: table %s {}}", "", "@8908828B")
	runNeg("table id inplace b", "/*HAT*/ table Monkey @8908828A {a: %s table {}}", "", "inplace")
	runNeg("table id inplace c", "union Monkey {a: table %s {}}", "", "@8908828B")
	runNeg("table id inplace d", "table Monkey @8908828A {a: union { a: table %s {}}}", "", "@8908828B")
	runNeg("table id inplace e", "table Monkey @8908828A {a: %s union { a: table {}}}", "", "inplace")
	runNeg("table id inplace f", "table Monkey @8908828A {a: %s union { a: {}}}", "", "inplace")

	runNeg("multi inplace", "table Monkey @8908828A {a: inplace Bytes; b: %s Text}", "inplace", "")


	runTest("validate base", lambda: runValidate("test/base.spr"))
	if runTest("cpp setup", lambda: runCppSetup("test/base.spr", "test/cpp.cc")):
		runTest("cpp out default simple", lambda: runCpp("out_default", "test/simple_default.bin"))
		runTest("cpp in default simple", lambda: runCpp("in_default", "test/simple_default.bin"))
		runTest("cpp out simple", lambda: runCpp("out", "test/simple.bin"))
		runTest("cpp in simple", lambda: runCpp("in", "test/simple.bin"))
		runTest("cpp out complex", lambda: runCpp("out_complex", "test/complex.bin"))
		runTest("cpp in complex", lambda: runCpp("in_complex", "test/complex.bin"))
		runTest("cpp out vl", lambda: runCpp("out_vl", "test/vl.bin"))
		runTest("cpp in vl", lambda: runCpp("in_vl", "test/vl.bin"))
		runTest("cpp out extend1", lambda: runCpp("out_extend1", "test/extend1.bin"))
		runTest("cpp in extend1", lambda: runCpp("in_extend1", "test/extend1.bin"))
		runTest("cpp out extend2", lambda: runCpp("out_extend2", "test/extend2.bin"))
		runTest("cpp in extend2", lambda: runCpp("in_extend2", "test/extend2.bin"))
	if runTest("py setup", lambda: runPySetup("test/base.spr")):
		runTest("py out default simple", lambda: runPy("out_default", "test/simple_default.bin"))
		runTest("py in default simple", lambda: runPy("in_default", "test/simple_default.bin"))
		runTest("py out simple", lambda: runPy("out", "test/simple.bin"))
		runTest("py in simple", lambda: runPy("in", "test/simple.bin"))
		runTest("py out complex", lambda: runPy("out_complex", "test/complex.bin"))
		runTest("py in complex", lambda: runPy("in_complex", "test/complex.bin"))
		runTest("py out vl", lambda: runPy("out_vl", "test/vl.bin"))
		runTest("py in vl", lambda: runPy("in_vl", "test/vl.bin"))
		runTest("py out extend1", lambda: runPy("out_extend1", "test/extend1.bin"))
		runTest("py in extend1", lambda: runPy("in_extend1", "test/extend1.bin"))
		runTest("py out extend2", lambda: runPy("out_extend2", "test/extend2.bin"))
		runTest("py in extend2", lambda: runPy("in_extend2", "test/extend2.bin"))

	print("="*80)
	if not failures:
		print("ALL GOOD")
		sys.exit(0)
	else:
		for t in failures:
			print("%s failed"%t)
		sys.exit(1)
		
if __name__ == '__main__':
	main()
