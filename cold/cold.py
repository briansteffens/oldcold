#!/usr/bin/env python3


class ReturnException(Exception):
	pass
class ImpossibleProgramException(Exception):
	pass
class ProgramFailedException(Exception):
	pass


class Case(object):
	def __init__(self, arg, expected):
		self.arg = arg
		self.expected = expected


class Function(object):
	def __init__(self, name, arg_count, code):
		self.name = name
		self.arg_count = arg_count
		self.code = code


class Job(object):
	def __init__(self):
		self.pattern_files = []
		self.depth = 1
		self.var_shadow = 1
		self.program_set_size = 1
		self.program_set = 1
		self.functions = {}
		self.constants = []
		self.constraints = {}
	@staticmethod
	def create(contents):
		ret = Job()
		for section in contents.split("!!"):
			if section[:8] == "patterns":
				for pattern_file in section[8:].split("\n"):
					pattern_file = pattern_file.strip()
					if pattern_file == "": continue
					ret.pattern_files.append(pattern_file)
			elif section[:5] == "depth":
				ret.depth = int(section[5:])
			elif section[:10] == "var_shadow":
				ret.var_shadow = int(section[10:])
			elif section[:16] == "program_set_size":
				ret.program_set_size = int(section[16:])
			elif section[:11] == "program_set":
				ret.program_set = int(section[11:])
			elif section[:9] == "functions":
				for function in section[9:].split("def "):
					function = function.strip()
					if function == "": continue
					lines = []
					first = True
					for line in function.split("\n"):
						if first:
							parts = line.split(" ")
							func_name = parts[0].strip()
							arg_count = parts[1].strip()
							first = False
							continue
						lines.append(line.strip())
					ret.functions[func_name] = Function(func_name, arg_count, "\n".join(lines))
			elif section[:9] == "constants":
				for constant in section[9:].split("\n"):
					constant = constant.strip()
					if constant == "": continue
					ret.constants.append(int(constant))
			elif section[:11] == "constraints":
				for constraint in section[11:].split("\n"):
					constraint = constraint.strip()
					if constraint == "": continue
					parts = constraint.split("=>")
					ret.constraints[int(parts[0].strip())] = int(parts[1].strip())
		return ret
	def save(self):
		ret = "!!depth "+str(self.depth)+"\n"
		ret += "!!var_shadow "+str(self.var_shadow)+"\n\n"
		ret += "!!program_set_size "+str(self.program_set_size)+"\n"
		ret += "!!program_set "+str(self.program_set)+"\n\n"
		ret += "!!patterns\n"
		for pattern_file in self.pattern_files:
			ret += "\t"+pattern_file+"\n"
		ret += "\n!!functions\n"
		for function in self.functions:
			ret += "def "+function+" 1\n"
			for line in self.functions[function].code.split("\n"):
				ret += "\t"+line+"\n"
		ret += "\n!!constants\n"
		for constant in self.constants:
			ret += "\t"+str(constant)+"\n"
		ret += "\n!!constraints\n"
		for constraint in self.constraints:
			ret += "\t" + str(constraint) + " => " + str(self.constraints[constraint]) + "\n"
		return ret

class Context(object):
	def __init__(self, job):
		self.job = job
		self.stat_unfinished = 0
		self.stat_runs = 0
		self.stat_states = 0
		self.stat_failed = 0
		self.solutions = []
	def run(self, program_sources):
		cases = []
		for p,v in self.job.constraints.items():
			cases.append(Case(p, v))

		def interpret(cases, case_index, source):
			interpreter = Interpreter(self, cases[case_index], source)
			for passed in interpreter.state_increment(interpreter.root_state):
				if case_index >= len(cases) - 1:
					yield passed
					break
				for passed2 in interpret(cases, case_index+1, passed):
					yield passed2
		
		for program_source in program_sources:
			for passed in interpret(cases, 0, program_source):
				self.solutions.append(passed)
				yield passed
	def print_stats(self):
		print("STATS {")
		print(str(self.stat_states) + " programs generated.")
		print(str(self.stat_runs) + " programs completed.")
		print(str(self.stat_failed) + " programs failed.")
		print(str(self.stat_unfinished) + " programs could not be finished.")
		print(str(len(self.solutions)) + " solutions found.")
		print("} STATS")

class Var(object):
	def __init__(self, var=None):
		self.name = None
		self.val = None
		self.last_set = None
		if var is not None:
			self.name = var.name
			self.val = var.val
			self.last_set = var.last_set
	@staticmethod
	def create(name,val,last_set):
		ret = Var()
		ret.name = name
		ret.val = val
		ret.last_set = last_set
		return ret


class Instruction(object):
	def __init__(self, line):
		self.code = line
		parts = line.split(" ")
		self.cmd = parts[0]
		self.params = parts[1:]
	def fhash(self):
		params = self.params[:]
		if self.cmd == "add" or self.cmd == "mul":
			temp = [params[0],params[1]]
			temp.sort()
			params[0] = temp[0]
			params[1] = temp[1]
		if self.cmd == "cmp":
			temp = [params[0],params[2]]
			temp.sort()
			params[0] = temp[0]
			params[2] = temp[1]
		ret = self.cmd + " " + " ".join(params)
		return ret
	def is_dumb(self):
		if self.cmd == "cmp":
			return self.params[0] == self.params[2]
		return False


class State(object):
	def __init__(self, context):
		self.context = context
		self.context.stat_states += 1
		self.lines = []
		self.inputs = {}
		self.outputs = {}
		self.locals = {}
		self.code_pointer = 0
		self.retval = None
		self.ended = False
		self.last_output_index = 0
		self.labels = {}
		self.expected = None
		self.lines_executed = -1
	def clone(self):
		ret = State(self.context)
		ret.lines = self.lines[:]
		ret.inputs = self.inputs.copy()
		ret.outputs = self.outputs.copy()
		ret.locals = self.locals.copy()
		ret.code_pointer = self.code_pointer
		ret.retval = self.retval
		ret.ended = self.ended
		ret.last_output_index = self.last_output_index
		ret.labels = self.labels.copy()
		ret.expected = self.expected
		ret.lines_executed = self.lines_executed
		return ret
	def check_for_expected(self):
		vardicts = [self.outputs,self.locals]
		for vardict in vardicts:
			for varname in vardict:
				if vardict[varname].val == self.expected:
					self.retval = vardict[varname]
					self.ended = True
					return varname
		raise ProgramFailedException()
	def find_labels(self):
		for i in range(len(self.lines)):
			line = self.lines[i]
			if line.code[-1] == ":":
				self.labels[line.code[:-1]] = i + 1
	def all_vars(self):
		ret = self.inputs.copy()
		ret.update(self.outputs)
		ret.update(self.context.job.constants)
		return ret
	def current_line(self):
		return self.lines[self.code_pointer]
	def execute(self, line):
		self.lines_executed += 1
		def evaluate(binding):
			try:
				return int(binding)
			except:
				if binding[0] == "l":
					return self.locals[binding].val
				try:
					return self.inputs[binding].val
				except:
					return self.outputs[binding].val
		def setvar(binding, val):
			d = None
			if binding[0] == "l":
				d = self.locals
			elif binding[0] == "i":
				d = self.inputs
			elif binding[0] == "o":
				d = self.outputs
			else:
				raise Exception("Misunderstood binding '" + binding + "'")
			if binding in d:
				d[binding].val = val
			else:
				d[binding] = Var.create(binding, val, self.code_pointer)
		if line.cmd[-1] == ":":
			return
		if line.cmd == "[ret]":
			self.lines[self.code_pointer] = Instruction("ret " + self.check_for_expected())
			self.retval = evaluate(self.current_line().params[0])
			self.ended = True
			raise ReturnException()
		elif line.cmd == "ret":
			self.retval = evaluate(line.params[0])
			raise ReturnException()
		elif line.cmd == "add":
			setvar(line.params[2], evaluate(line.params[0]) + evaluate(line.params[1]))
		elif line.cmd == "mul":
			setvar(line.params[2], evaluate(line.params[0]) * evaluate(line.params[1]))
		elif line.cmd == "cmp":
			left = evaluate(line.params[0])
			right = evaluate(line.params[2])
			if line.params[1] == "==":
				cmpres = left == right
			elif line.params[1] == "!=":
				cmpres = left != right
			elif line.params[1] == ">":
				cmpres = left > right
			elif line.params[1] == "<":
				cmpres = left < right
			else:
				raise Exception("Unknown comparison [" + cmpres + "] in [" + line.code + "].")
			if cmpres:
				return self.labels[line.params[3]]
		elif line.cmd == "jmp":
			return self.labels[line.params[0]]
		else:
			raise Exception("Unknown command in [" + line.code + "].")
	def all_code(self):
		ret = ""
		for line in self.lines:
			if ret != "": ret += "\n"
			ret += line.code
		return ret
		

class Interpreter(object):
	def __init__(self, context, case, code):
		self.context = context
		self.case = case
		self.root_state = State(context)
		self.root_state.expected = case.expected
		self.root_state.inputs["p1"] = Var.create("p1", case.arg, 0)
		self.states = [self.root_state]
		self.ended = []
		self.last_retval = None
		for line in code.split("\n"):
			line = line.strip()
			if line == "": continue
			self.root_state.lines.append(Instruction(line))
			self.root_state.find_labels()
	
	def state_increment(self, state):
		if state.ended: return
		if state.current_line().code == "[ret]" or "[" not in state.current_line().code:
			try:
				res = state.execute(state.current_line())
			except ReturnException as e:
				state.ended = True
				self.context.stat_runs += 1
				self.last_retval = state.retval
				if state.retval == self.case.expected:
					yield state.all_code()
				return
			except ProgramFailedException as e:
				state.ended = True
				self.context.stat_failed += 1
				return
			except Exception as e:
				print(state.all_code())
				raise e

			if res is None:
				state.code_pointer += 1
			else:
				state.code_pointer = res
		
		try:
			temps = self.replacer(state)
		except ImpossibleProgramException as e:
			self.context.stat_unfinished += 1
			return
			
		for temp in temps:
			for ret in self.state_increment(temp):
				yield ret
			
	
	def run(self):
		while True:
			count_running = 0
			for state in self.states:
				if not state.ended:
					count_running += 1
			if count_running == 0:
				break
					
			states = self.states[:]
			new_states = []
			
			while len(states) > 0:
				state = states.pop(0)
				if state.ended:
					new_states.append(state)
					continue
				
				try:
					temps = self.replacer(state)
				except ImpossibleProgramException as e:
					self.context.stat_unfinished += 1
					continue
					
				for temp in temps:
					new_states.append(temp)
					try:
						res = temp.execute(temp.current_line())
					except ReturnException as e:
						temp.ended = True
						self.context.stat_runs += 1
						self.last_retval = temp.retval
						if temp.retval == self.case.expected:
							yield temp.all_code()
						continue
					except ProgramFailedException as e:
						temp.ended = True
						self.context.stat_failed += 1
						continue
					except Exception as e:
						print(temp.all_code())
						raise e
		
					if res is None:
						temp.code_pointer += 1
					else:
						temp.code_pointer = res
			
			self.states = new_states
	def input_eval(self, state, val):
		ret = []
		for rep in val.split("|"):
			if rep == "c":
				for constant in self.context.job.constants:
					ret.append(constant)
			elif rep == "o":
				for var in state.outputs:
					v = state.outputs[var]
					if state.code_pointer - v.last_set <= self.context.job.var_shadow:
						ret.append(var)
			elif rep[0] == "i":
				for var in state.inputs:
					v = state.inputs[var]
					if state.code_pointer - v.last_set <= self.context.job.var_shadow:
						ret.append(var)
			elif rep == "cmp":
				ret.extend(["==","!="])
			else:
				raise Exception("Unknown: [" + val + "]")
		return ret
	def product(self, left, right):
		ret = []
		for l in left:
			for r in right:
				ret.append(l+(r,))
		return ret
	def strip_dumb_instructions(self, instructions):
		already = []
		for i in reversed(range(len(instructions))):
			inst = instructions[i]
			fhash = inst.fhash()
			if fhash in already or inst.is_dumb():
				instructions.pop(i)
				continue
			already.append(fhash)
		return instructions
			
	def replacer(self, state):
		if state.current_line().code == "[ret]":
			return [state]
		parts = [""]
		bracket = False
		for c in state.current_line().code:
			if c == "[" or c == "]":
				parts.append("")
				continue
			parts[len(parts)-1] += c
		if len(parts) == 1:
			return [state]
		options = {}
		combos = None
		combo_to_parts = {}
		j = -1
		for i in range(1,len(parts),2):
			if parts[i][0] in "ivoc":
				options[i] = self.input_eval(state, parts[i])
				if len(options[i]) == 0:
					raise ImpossibleProgramException("'" + parts[i] + "' can't be replaced in '" + state.current_line().code + "'")
				j += 1
				combo_to_parts[j] = i
				if combos is None:
					combos = []
					for option in options[i]:
						combos.append((option,))
					continue
				combos = self.product(combos, options[i])
		
		lines = []
		for combo in combos:
			parts_temp = parts[:]
			for c, p in combo_to_parts.items():
				parts_temp[p] = str(combo[c])
			lines.append(Instruction("".join(parts_temp)))
		
		ret = []
		lines = self.strip_dumb_instructions(lines)
		for line in lines:
			new_state = state.clone()
			new_state.lines[new_state.code_pointer] = line
			ret.append(new_state)
		
		return ret
		


# non-parallel mode
def run_linear(codefile, p1):
	parts = codefile.split("\n")
	left = []
	for part in parts:
		part = part.strip()
		if part == "": continue
		if part[0] == "#": continue
		left.append(part)
	codefile = "\n".join(left)
	funcs = codefile.split("def ")
	for i in range(len(funcs)):
		func = funcs[i]
		if func[:6] == "main 1":
			temp = func[6:].split("\n")
			main_code = ""
			for t in temp:
				t = t.strip()
				if t == "": continue
				main_code += t + "\n"
			main_index = i
	funcs.pop(main_index)
	funcs2 = []
	for func in funcs:
		if func != "":
			funcs2.append(func)
	funcs = funcs2
	job = Job.create("!!functions\n" + "def ".join(funcs))
	context = Context(job)
	case = Case(p1, None)
	interpreter = Interpreter(context, case, main_code)
	for output in interpreter.run():
		pass
	return interpreter.last_retval





class Pattern(object):
	def __init__(self, template):
		self.template = template.strip() + "\n"
		self.replacers = []
		in_bracket = False
		replacer = ""
		for c in self.template:
			if c == "[":
				replacer = ""
				in_bracket = True
				continue
			if c == "]":
				self.replacers.append(replacer)
				in_bracket = False
				continue
			replacer += c






class Assembler(object):
	@staticmethod
	def process_jumps(pattern, jumps):
		template = ""
		in_brackets = False
		param = ""
		local_jumps = {}
		for c in pattern:
			if c == "[":
				in_brackets = True
				continue
			if c == "]":
				if param[0] == "j":
					if param not in local_jumps:
						for j in range(100000):
							new_jump = "j" + str(j)
							found = False
							for jump in jumps:
								if jumps[jump] == new_jump:
									found = True
									break
							if not found: break
						local_jumps[param] = new_jump
						jumps[new_jump] = new_jump
					template += local_jumps[param]
				else:			
					template += "[" + param + "]"
				param = ""
				in_brackets = False
				continue
			if in_brackets:
				param += c
			else:
				template += c
		return template
	@staticmethod
	def process_locals(pattern, all_locals):
		template = ""
		in_brackets = False
		param = ""
		local_locals = {}
		for c in pattern:
			if c == "[":
				in_brackets = True
				continue
			if c == "]":
				if param[0] == "l":
					if param not in local_locals:
						for j in range(100000):
							new_local = "l" + str(j)
							found = False
							for local in all_locals:
								if all_locals[local] == new_local:
									found = True
									break
							if not found: break
						local_locals[param] = new_local
						all_locals[new_local] = new_local
					template += local_locals[param]
				else:
					template += "[" + param + "]"
				param = ""
				in_brackets = False
				continue
			if in_brackets:
				param += c
			else:
				template += c
		return template
	
	@staticmethod
	def structure(assembly, patterns, pattern_list, jumps={}, _locals={}):
		if assembly is None:
			assembly = Assembler.process_locals(Assembler.process_jumps(patterns[pattern_list.pop(0)].template, jumps), _locals)

		new_assembly = ""
		in_bracket = False
		param = ""
		for c in assembly:
			if c == "[":
				in_bracket = True
				continue
			if c == "]":
				if param == "next":
					if len(pattern_list) > 0:
						pattern = patterns[pattern_list.pop(0)].template
						pattern = Assembler.process_jumps(pattern, jumps)
						pattern = Assembler.process_locals(pattern, _locals)
						new_assembly += pattern
					else:
						new_assembly += "[next]"
				else:
					new_assembly += "[" + param + "]"
				in_bracket = False
				param = ""
				continue
			if in_bracket:
				param += c
			else:
				new_assembly += c
	
		if len(pattern_list) == 0 or "[next]" not in new_assembly:
			return new_assembly
		return Assembler.structure(new_assembly, patterns, pattern_list, jumps=jumps, _locals=_locals)

	@staticmethod
	def outs(assembly):
		lines = assembly.split("\n")
		new_lines = []
		last_output_index = 0
		for orig_line in lines:
			in_bracket = False
			line = ""
			param = ""
			for c in orig_line:
				if c == "[":
					in_bracket = True
					continue
				if c == "]":
					if param == "o":
						line += "o" + str(last_output_index)
						last_output_index += 1
					else:			
						line += "[" + param + "]"
					param = ""
					in_bracket = False
					continue
				if in_bracket:
					param += c
				else:
					line += c
			new_lines.append(line)

		return "\n".join(new_lines)

	@staticmethod
	def finish(assembly):
		parts = assembly.split("[next]")
		i = 1
		while True:
			if i >= len(parts): break
			parts.insert(i, "[ret]")
			i += 2
		return "".join(parts)

	@staticmethod
	def product(patterns, depth, start=0):
		val = []
		while start:
			val.append(int(start % patterns))
			start = int(start / patterns)
		val.reverse()
		while len(val) < depth:
			val.insert(0, 0)
	
		def inc(v, i=depth-1):
			v[i] += 1
			if v[i] > patterns-1:
				v[i] = 0
				if i == 0: raise OverflowError()
				return inc(v,i-1)
			return v
	
		while True:
			yield val
			try:
				val = inc(val)
			except OverflowError:
				break

	@staticmethod
	def assemble(job):
		from datetime import datetime, timedelta
		patterns = []
		for pattern_file in job.pattern_files:
			with open(pattern_file + ".patterns") as f:
				for pattern_code in f.read().split("-----"):
					patterns.append(Pattern(pattern_code.strip()))

		program_start = job.program_set_size * (job.program_set - 1)
		program_num = -1
		taken = timedelta(seconds=0)
		for pattern_tuple in Assembler.product(len(patterns), job.depth, program_start):
			program_num += 1
			pattern_list = []
			for i in pattern_tuple:
				pattern_list.append(i)
			before = datetime.now()
			yield Assembler.finish(Assembler.outs(Assembler.structure(None, patterns, pattern_list,jumps={},_locals={}))).strip()
			taken += datetime.now() - before
			if program_num >= job.program_set_size - 1:
				break





