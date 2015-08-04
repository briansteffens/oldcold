#!/usr/bin/env python3

import sys, argparse


class Program(object):
	
	def __init__(self, source_code):
		self.subs = {}
		
		current_sub = None
		
		source = source_code.split("\n")
		
		for code in source:
			code = code.strip()
	
			if code == "":
				continue
			
			if code[0] == "#":
				continue
			
			if code[-1] == ":":
				current_sub = code[:-1]
				self.subs[current_sub] = []
				continue
	
			if current_sub is None:
				raise Exception("Line outside sub: " + code)
			
			without_conditional = code
			if ")" in without_conditional:
				without_conditional = without_conditional.split(")")[1].strip()
			
			line = None
			
			if without_conditional[:7] == "superbu":
				line = SuperbuLine(code)
			if without_conditional[:5] == "print":
				line = PrintLine(code)
			if without_conditional[:4] == "jump":
				line = JumpLine(code)
			if without_conditional[:6] == "return":
				line = ReturnLine(code)
			if without_conditional[:3] == "set":
				line = SetLine(code)
			if without_conditional[:4] == "push":
				line = PushLine(code)
			if without_conditional[:3] == "pop":
				line = PopLine(code)
			if without_conditional[:5] == "stash":
				line = StashLine(code)
			if without_conditional[:7] == "restore":
				line = RestoreLine(code)
			if without_conditional[:3] == "and":
				line = AndLine(code)
			if without_conditional[:6] == "buffer":
				line = BufferLine(code)
			if without_conditional[:4] == "kill":
				line = KillLine(code)
			if without_conditional[:4] == "read":
				line = ReadLine(code)
			if without_conditional[:5] == "write":
				line = WriteLine(code)
			
			if line is None:
				raise Exception("Unable to parse line: " + code)
	
			self.subs[current_sub].append(line)
		


class Line(object):
	def __init__(self, code):
		self.conditional = ""
		self.code = ""
		in_paren = False
		for c in code:
			if c == "(":
				in_paren = True
				continue
			elif c == ")":
				in_paren = False
				continue
			if in_paren:
				self.conditional += c
			else:
				self.code += c
		self.code = self.code.strip()
		self.conditional = self.conditional.strip()
		
	def execute(self, context):
		raise NotImplementedError("Command in [" + self.code + "] unimplemented.")

class PrintLine(Line):
	def execute(self, context):
		args = self.code[6:]
		for var in context.vars:
			args = args.replace("$" + var, str(context.vars[var]))
		print(args)

class SuperbuLine(Line):
	def execute(self, context):
		exit()

class JumpLine(Line):
	def execute(self, context):
		return self.code[5:]

class ReturnLine(Line):
	def execute(self, context):
		return -1

class SetLine(Line):
	def execute(self, context):
		args = self.code[4:]
		parts = args.split("=")
		
		var = parts[0].strip()
		val = parts[1].strip()
		
		context.vars[var] = context.evaluate(val)

class PushLine(Line):
	def execute(self, context):
		args = self.code[4:].split(",")
		for arg in args:
			context.stack.append(context.evaluate(arg.strip()))
		
class PopLine(Line):
	def execute(self, context):
		args = self.code[3:].split(",")
		for i in range(len(args) - 1, -1, -1):
			context.vars[args[i].strip()] = context.stack.pop()

class StashLine(Line):
	def execute(self, context):
		context.stack.append(context.vars["ax"])
		context.stack.append(context.vars["bx"])
		context.stack.append(context.vars["cx"])
		context.stack.append(context.vars["dx"])		
		
class RestoreLine(Line):
	def execute(self, context):
		context.vars["dx"] = context.stack.pop()
		context.vars["cx"] = context.stack.pop()
		context.vars["bx"] = context.stack.pop()
		context.vars["ax"] = context.stack.pop()

class AndLine(Line):
	def execute(self, context):
		args = self.code[3:].split(">")
		dest = args[1].strip()
		sources = args[0].split(",")
		left = context.evaluate(sources[0].strip())
		right = context.evaluate(sources[1].strip())
		context.vars[dest] = int(bool(left) & bool(right))

class BufferLine(Line):
	def execute(self, context):
		args = self.code[6:].strip().split(" ")
		buffer = args[0].strip()
		length = context.evaluate(args[1].strip())
		context.vars[buffer] = []
		for i in range(length):
			context.vars[buffer].append(0)
			
class KillLine(Line):
	def execute(self, context):
		context.vars.pop(self.code[4:].strip(), None)

class ReadLine(Line):
	def execute(self, context):
		args = self.code[4:].strip().split(" ")
		buffer = args[0].strip()
		index = context.evaluate(args[1].strip())
		dest = args[2].strip()
		context.vars[dest] = context.vars[buffer][index]

class WriteLine(Line):
	def execute(self, context):
		args = self.code[5:].strip().split(" ")
		buffer = args[0].strip()
		index = context.evaluate(args[1].strip())
		val = context.evaluate(args[2].strip())
		context.vars[buffer][index] = val

class Context(object):
	def __init__(self):
		self.vars = {"ax": 0,"bx": 0,"cx": 0,"dx": 0}
		self.stack = []
	def evaluate(self, expr):
		inc = 0
		while True:
			if expr[-1:] == "+":
				inc += 1
			elif expr[-1:] == "-":
				inc -= 1
			else:
				break
			expr = expr[:-1]
		
		expr = expr.strip()
		
		if expr[0] == "$":
			val = self.vars[expr[1:].strip()]
		else:
			val = int(expr)
		
		val += inc
		
		return val
	def compare(self, expr):
		if "==" in expr:
			comparison = "=="
		elif "!=" in expr:
			comparison = "!="
		elif "<" in expr:
			comparison = "<"
		elif ">" in expr:
			comparison = ">"
		else:
			raise Exception("Comparison operator not found in [" + expr + "].")
		
		parts = expr.split(comparison)
		
		left = self.evaluate(parts[0])
		right = self.evaluate(parts[1])

		if comparison == "==":		
			return left == right
		elif comparison == "!=":
			return left != right
		elif comparison == "<":
			return left < right
		elif comparison == ">":
			return left > right



class Interpreter(object):
	def __init__(self, program, context=Context()):
		self.program = program
		self.context = context
		self.call_stack = []
	
	def code_pointer(self):
		return self.call_stack[-1]
	
	def run(self):
		if not "bu" in self.program.subs:
			raise Exception("No 'bu' sub in program -.-")
		
		self.call_stack.append({
			"sub": self.program.subs["bu"],
			"line": 0
		})
		
		while True:
			if len(self.call_stack) == 0:
				break
			
			ptr = self.code_pointer()
					
			if ptr["line"] >= len(ptr["sub"]):
				self.call_stack.pop()
				continue
			
			line = ptr["sub"][ptr["line"]]

			execute = True
			if line.conditional != "":
				execute = self.context.compare(line.conditional)
			
			if execute:
				exec_result = line.execute(self.context)
			
			ptr["line"] += 1
			
			if not execute:
				continue
				
			
			# Return
			if exec_result == -1:
				self.call_stack.pop()
			
			# No call stack change
			elif exec_result is None:
				pass
			
			# Jump
			else:
				self.call_stack.append({
					"sub": self.program.subs[exec_result],
					"line": 0
				})


with open(sys.argv[1], "r") as f:
	Interpreter(Program(f.read())).run()




