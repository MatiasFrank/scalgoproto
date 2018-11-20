# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
"""
Generate python reader/wirter
"""
from parser import Parser, ParseError
from annotate import annotate
from parser import TokenType, NodeType, Token, Struct, AstNode, Value, Enum, Table, VLUnion, VLList, VLBytes, VLText
from typing import Set, Dict, List, TextIO, Tuple, Union, NamedTuple
from types import SimpleNamespace
import math
from util import cescape, getuname

TypeInfo = NamedTuple("TypeInfo", [("n",str), ("p",str),("s",str),("w",int)])

typeMap: Dict[TokenType, TypeInfo] = {
	TokenType.INT8: TypeInfo("Int8", "int", "b", 1),
	TokenType.INT16: TypeInfo("Int16", "int", "h", 2),
	TokenType.INT32: TypeInfo("Int32", "int", "i", 4),
	TokenType.INT64: TypeInfo("Int64", "int", "q", 8),
	TokenType.UINT8: TypeInfo("UInt8", "int", "B", 1),
	TokenType.UINT16: TypeInfo("UInt16", "int", "H", 2),
	TokenType.UINT32: TypeInfo("UInt32", "int", "I", 4),
	TokenType.UINT64: TypeInfo("UInt64", "int", "Q", 8),
	TokenType.FLOAT32: TypeInfo("Float32", "float", "f", 4),
	TokenType.FLOAT64: TypeInfo("Float64", "float", "d", 8),
	TokenType.BOOL: TypeInfo("Bool", "bool", "?", 1),
}

class Generator:
	out: TextIO = None

	def outListType(self, node:Union[Value,VLList]) -> str:
		if node.type.type == TokenType.BOOL:
			assert False # TODO bool list
		elif node.type.type in typeMap:
			return "scalgoproto.BasicListOut[%s]"%(typeMap[node.type.type].p)
		elif node.type.type == TokenType.IDENTIFIER:
			if node.struct:
				return "scalgoproto.StructListOut[%s]"%(self.value(node.type))
			elif node.enum:
				return "scalgoproto.EnumListOut[%s]"%(self.value(node.type))
			elif node.table:
				return "scalgoproto.ObjectListOut[%sOut]"%(self.value(node.type))
			else:
				assert False
		elif node.type.type == TokenType.TEXT:
			return "scalgoproto.ObjectListOut[scalgoproto.TextOut]"
		elif node.type.type == TokenType.BYTES:
			return "scalgoproto.ObjectListOut[scalgoproto.BytesOut]"
		else:
			assert False

	def inListHelp(self, node:Union[Value,VLList], os:str) -> Tuple[str, str]:
		tn = self.value(node.type)
		if node.type.type == TokenType.BOOL:
			assert False # TODO bool list
		elif node.type.type in (TokenType.FLOAT32, TokenType.FLOAT64):
			ti = typeMap[node.type.type]
			return (ti.p, "\t\treturn self._reader._getFloatList('%s', %d, %s)"%(ti.s, ti.w, os))
		elif node.type.type in typeMap:
			ti = typeMap[node.type.type]
			return (ti.p, "\t\treturn self._reader._getIntList('%s', %d, %s)"%(ti.s, ti.w, os))
		elif node.type.type == TokenType.IDENTIFIER:
			if node.struct:
				return (tn, "\t\treturn self._reader._getStructList(%s, %s,)"%(tn, os))
			elif node.enum:
				return (tn, "\t\treturn self._reader._getEnumList(%s, %s)"%(tn, os))
			elif node.table:
				return (tn+"In", "\t\treturn self._reader._getTableList(%sIn, %s)"%(tn, os))
			else:
				assert False
		elif node.type.type == TokenType.TEXT:
			return ("str", "\t\treturn self._reader._getTextList(%s)"%(os))
		elif node.type.type == TokenType.BYTES:
			return ("bytes", "\t\treturn self._reader._getBytesList(%s)"%(os))
		else:
			assert False

	def o(self, text=""):
		print(text, file=self.out)
	
	def __init__(self, data:str, out:TextIO) -> None:
		self.data = data
		self.out = out
		
	def value(self, t:Token) -> str:
		return self.data[t.index: t.index + t.length]

	def outputDoc(self, node: AstNode, indent:str="", prefix:List[str] = [], suffix:List[str] = []):
		if not node.docstring and not suffix and not prefix: return	
		self.o('%s"""'%indent)
		for line in prefix:
			self.o("%s%s"%(indent,line))
		if prefix and (node.docstring or suffix):
			self.o("%s"%indent)
		if node.docstring:
			for line in node.docstring:
				self.o("%s%s"%(indent, line))
		if node.docstring and suffix:
			self.o("%s"%indent)
		for line in suffix:
			self.o("%s%s"%(indent, line))
		self.o('%s"""'%indent)
	
	def generateValueIn(self, node: Value):
		n = self.value(node.identifier)
		uname = getuname(n)
		if node.list:
			self.o("\tdef has%s(self) -> bool: return self._getUInt32(%d, 0) != 0"%(uname, node.offset))
			(tn, acc) = self.inListHelp(node, "*self._getList(%d)"%node.offset)
			self.o("\tdef get%s(self) -> scalgoproto.ListIn[%s]:"%(uname, tn))
			self.outputDoc(node, "\t\t")
			self.o("\t\tassert self.has%s()"%uname)
			self.o(acc)
			self.o("")
		elif node.type.type == TokenType.BOOL:
			if node.optional:
				self.o("\tdef has%s(self) -> bool: return self._getBit(%d, %s, 0)"%(uname, node.hasOffset, node.hasBit))
			self.o("\tdef get%s(self) -> bool:"%(uname))
			self.outputDoc(node, "\t\t")
			if node.optional:
				self.o("\t\tassert self.has%s()"%uname)
			self.o("\t\treturn self._getBit(%d, %s, 0)"%(node.offset, node.bit))
			self.o("\t")
		elif node.type.type in typeMap:
			ti = typeMap[node.type.type]
			if node.optional:
				if node.type.type in (TokenType.FLOAT32, TokenType.FLOAT64):
					self.o("\tdef has%s(self) -> bool: return not math.isnan(self._get%s(%d, math.nan))"%(uname, ti.n, node.offset))
				else:
					self.o("\tdef has%s(self) -> bool: return self._getBit(%d, %s, 0)"%(uname, node.hasOffset, node.hasBit))
			self.o("\tdef get%s(self) -> %s:"%(uname, ti.p))
			self.outputDoc(node, "\t\t")
			if node.optional:
				self.o("\t\tassert self.has%s()"%uname)
			self.o("\t\treturn self._get%s(%d, %s)"%(ti.n, node.offset, node.parsedValue if not math.isnan(node.parsedValue) else "math.nan"))
			self.o("\t")
		elif node.type.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type)
			if node.enum:
				self.o("\tdef has%s(self) -> bool: return self._getUInt8(%d, %d) != 255"%(uname, node.offset, node.parsedValue))
				self.o("\tdef get%s(self) -> %s:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				self.o("\t\tassert self.has%s()"%uname)
				self.o("\t\treturn %s(self._getUInt8(%d, %s))"%(typeName, node.offset, node.parsedValue))
				self.o("\t")
			elif node.struct:
				if node.optional:
					self.o("\tdef has%s(self) -> bool: return self._getBit(%d, %s, 0)"%(uname, node.hasOffset, node.hasBit))
				self.o("\tdef get%s(self) -> %s:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				if node.optional:
					self.o("\t\tassert self.has%s()"%uname)
				self.o("\t\treturn %s._read(self._reader, self._offset+%d) if self._offset < self._size else %s()"%(typeName, node.offset, typeName))
				self.o("\t")
			elif node.table:
				self.o("\tdef has%s(self) -> bool: return self._getUInt32(%d, 0) != 0"%(uname, node.offset))
				self.o("\tdef get%s(self) -> %sIn:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				self.o("\t\tassert self.has%s()"%uname)
				self.o("\t\treturn self._getTable(%sIn, %d)"%(typeName, node.offset))
				self.o("\t")
			else:
				assert False
		elif node.type.type == TokenType.TEXT:
			self.o("\tdef has%s(self) -> bool: return self._getUInt32(%d, 0) != 0"%(uname, node.offset))
			self.o("\tdef get%s(self) -> str:"%(uname))
			self.outputDoc(node, "\t\t")
			self.o("\t\tassert self.has%s()"%(uname))
			self.o("\t\treturn self._getText(%d)"%(node.offset))
			self.o("\t")
		elif node.type.type == TokenType.BYTES:
			self.o("\tdef has%s(self) -> bool: return self._getUInt32(%d, 0) != 0"%(uname, node.offset))
			self.o("\tdef get%s(self) -> bytes:"%(uname))
			self.outputDoc(node, "\t\t")
			self.o("\t\tassert self.has%s()"%(uname))
			self.o("\t\treturn self._getBytes(%d)"%(node.offset))
			self.o("\t")
		else:
			assert False

	def generateValueOut(self, node:Value):
		n = self.value(node.identifier)
		uname = n[0].upper() + n[1:]
		if node.list:
			self.o("\tdef add%s(self, value: %s):"%(uname, self.outListType(node)))
			self.outputDoc(node, "\t\t")
			self.o("\t\tself._setList(%d, value)"%(node.offset))
			self.o("\t")
		elif node.type.type == TokenType.BOOL:
			self.o("\tdef add%s(self, value:bool) -> None:"%(uname))
			self.outputDoc(node, "\t\t")
			if node.optional:
				self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
			self.o("\t\tif value: self._setBit(%d, %d)"%(node.offset, node.bit))
			self.o("\t\telse: self._unsetBit(%d, %d)"%(node.offset, node.bit))
			self.o("\t")
		elif node.type.type in typeMap:
			ti = typeMap[node.type.type]
			self.o("\tdef add%s(self, value: %s) -> None:"%(uname, ti.p))
			self.outputDoc(node, "\t\t")
			if node.optional and node.type.type not in (TokenType.FLOAT32, TokenType.FLOAT64):
				self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
			self.o("\t\tself._set%s(%d, value)"%(ti.n, node.offset))
			self.o("\t")
		elif node.type.type == TokenType.IDENTIFIER:
			typeName = self.value(node.type)
			if node.enum:
				self.o("\tdef add%s(self, value: %s) -> None:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				self.o("\t\tself._setUInt8(%d, int(value))"%(node.offset))
				self.o("\t")
			elif node.struct:
				self.o("\tdef add%s(self, value: %s) -> None:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				if node.optional:
					self.o("\t\tself._setBit(%d, %d)"%(node.hasOffset, node.hasBit))
				self.o("\t\t%s._write(self._writer, self._offset + %d, value)"%(typeName, node.offset))
				self.o("\t")
			elif node.table:
				self.o("\tdef add%s(self, value: %sOut) -> None:"%(uname, typeName))
				self.outputDoc(node, "\t\t")
				self.o("\t\tself._setTable(%d, value)"%(node.offset))
				self.o("\t")
			else:
				assert False
		elif node.type.type == TokenType.TEXT:
			self.o("\tdef add%s(self, t: scalgoproto.TextOut) -> None:"%(uname))
			self.outputDoc(node, "\t\t")
			self.o("\t\tself._setText(%d, t)"%(node.offset))
			self.o("\t")
		elif node.type.type == TokenType.BYTES:
			self.o("\tdef add%s(self, b: scalgoproto.BytesOut) -> None:"%(uname))
			self.outputDoc(node, "\t\t")
			self.o("\t\tself._setBytes(%d, b)"%(node.offset))
			self.o("\t")
		else:
			assert False

	def generateVLUnionIn(self, node: VLUnion, tableName:str):
		self.o("\tclass Type(enum.IntEnum):")
		self.o("\t\tNONE = 0")
		idx = 1
		for member in node.members:
			assert isinstance(member, (Table, Value))
			self.o("\t\t%s = %d"%(self.value(member.identifier).upper(), idx))
			idx += 1
		self.o("\t")
		self.o("\tdef getType(self) -> Type:")
		self.outputDoc(node, "\t")
		self.o("\t\treturn %sIn.Type(self._getUInt16(%d, 0))"%(tableName, node.offset))
		self.o("\t")
		self.o("\tdef hasType(self) -> bool: return self.getType() != %sIn.Type.NONE"%(tableName))
		for member in node.members:
			assert isinstance(member, (Table, Value))
			n = self.value(member.identifier)
			uname = n[0].upper() + n[1:]
			table = member.table if isinstance(member, Value) else member
			self.o("\tdef is%s(self) -> bool: return self.getType() == %sIn.Type.%s"%(uname, tableName, n.upper()))
			if table.values:
				self.o("\t")
				self.o("\tdef get%s(self) -> %sIn:"%(uname, table.name))
				self.outputDoc(node, "\t\t")
				self.o("\t\tassert self.is%s()"%(uname))
				self.o("\t\treturn self._getVLTable(%sIn, %d)"%(table.name, node.offset+2))
				self.o("\t")

	def generateVLUnionOut(self, node:VLUnion):
		self.outputDoc(node, "\t")
		self.o("\tdef hasType(self) -> bool: return self._getUInt16(%d) != 0"%node.offset)
		idx = 1
		for member in node.members:
			assert isinstance(member, (Table, Value))
			n = self.value(member.identifier)
			uname = n[0].upper() + n[1:]
			tbl = member.table if isinstance(member, Value) else member
			if tbl.values:
				self.o("\tdef add%s(self) -> %sOut:"%(uname, tbl.name))
				self.outputDoc(member, "\t\t")
				self.o("\t\tassert not self.hasType()")
				self.o("\t\tself._setUInt16(%d, %d)"%(node.offset, idx))
				self.o("\t\tself._setUInt32(%d, %d)"%(node.offset+2, len(tbl.default)))
				self.o("\t\treturn self._constructUnionMember(%sOut)"%tbl.name)
				self.o("\t")
			else:
				self.o("\tdef add%s(self) -> None:"%(uname))
				self.outputDoc(member, "\t\t")
				self.o("\t\tassert not self.hasType()")
				self.o("\t\tself._setUInt16(%d, %d)"%(node.offset, idx))
				self.o("\t\tself._setUInt32(%d, %d)"%(node.offset+2, 0))
				self.o("\t")
			idx += 1

	def generateVLBytesIn(self, node:VLBytes):
		self.o("\tdef hasBytes(self) -> bool: return self._getUInt32(%d, 0) != 0"%(node.offset))
		self.o("\tdef getBytes(self) -> bytes:")
		self.outputDoc(node, "\t\t")
		self.o("\t\tassert self.hasBytes()")
		self.o("\t\treturn self._getVLBytes(%d)"%(node.offset))
		self.o("\t")

	def generateVLBytesOut(self, node:VLBytes):
		self.o("\tdef addBytes(self, value: bytes) -> None:")
		self.outputDoc(node, "\t\t")
		self.o("\t\tself._addVLBytes(%d, value)"%(node.offset))
		self.o("\t")

	def generateVLListIn(self, node:VLList):
		self.o("\tdef hasList(self) -> bool: return self._getUInt32(%d, 0) != 0"%(node.offset))
		(tn, acc) = self.inListHelp(node, "self._offset + self._size, self._getUInt32(%d, 0)"%node.offset)
		self.o("\tdef getList(self) -> scalgoproto.ListIn[%s]:"%(tn))
		self.outputDoc(node, "\t\t")
		self.o("\t\tassert self.hasList()")
		self.o(acc)
		self.o("")

	def generateVLListOut(self, node:VLList):
		self.o("\tdef addList(self, size: int) -> %s:"%(self.outListType(node)))
		self.outputDoc(node, "\t\t")
		cons = None
		tname = self.value(node.type)
		if node.type.type in typeMap:
			ti = typeMap[node.type.type]
			self.o("\t\tl = scalgoproto.BasicListOut[%s](self._writer, '%s', %d, size, False)"%(ti.p, ti.s, ti.w))
		elif node.enum:
			self.o("\t\tl = scalgoproto.EnumListOut[%s](self._writer, %s, size, False)"%(tname, tname))
		elif node.struct:
			self.o("\t\tl = scalgoproto.StructListOut[%s](self._writer, %s, size, False)"%(tname, tname))
		elif node.table:
			self.o("\t\tl = scalgoproto.ObjectListOut[%sOut](self._writer, size, False)"%(tname))
		elif node.type.type == TokenType.TEXT:
			self.o("\t\tl = scalgoproto.ObjectListOut[TextOut](self._writer, size, False)")
		elif node.type.type == TokenType.BYTES:
			self.o("\t\tl = scalgoproto.ObjectListOut[TextOut](self._writer, size, False)")
		self.o("\t\tself._setVLList(%d, size)"%(node.offset))
		self.o("\t\treturn l")
		self.o("\t")

	def generateVLTextIn(self, node:VLText):
		self.o("\tdef hasText(self) -> bool: return self._getUInt32(%d, 0) != 0"%(node.offset))
		self.outputDoc(node, "\t")
		self.o("\tdef getText(self) -> str:")
		self.o("\t\tassert self.hasText()")
		self.o("\t\treturn self._getVLText(%d)"%(node.offset))
		self.o("\t")

	def generateVLTextOut(self, node:VLText):
		self.o("\tdef addText(self, text:str) -> None:")
		self.outputDoc(node, "\t\t")
		self.o("\t\tself._addVLText(%d, text)"%(node.offset))
		self.o("\t")

	def generateTable(self, table:Table):
		# Recursivly generate contained VL tabels
		for node in table.values:
			if node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				for member in node.members:
					if member.t == NodeType.TABLE:
						assert isinstance(member, Table)
						if member.values:
							self.generateTable(member)

		# Generate table reader
		self.o("class %sIn(scalgoproto.TableIn):"%table.name)
		self.outputDoc(table, "\t")
		self.o("\t_MAGIC:typing.ClassVar[int]=0x%08x"%table.magic)
		self.o("\tdef __init__(self, reader: scalgoproto.Reader, offset:int, size:int):")
		self.o('\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""')
		self.o("\t\tsuper().__init__(reader, offset, size)")
		for node in table.values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				self.generateValueIn(node)
			elif node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				self.generateVLUnionIn(node, table.name)
			elif node.t == NodeType.VLBYTES:
				assert isinstance(node, VLBytes)
				self.generateVLBytesIn(node)
			elif node.t == NodeType.VLLIST:
				assert isinstance(node, VLList)
				self.generateVLListIn(node)
			elif node.t == NodeType.VLTEXT:
				assert isinstance(node,VLText)
				self.generateVLTextIn(node)
			else:
				assert(False)
		self.o("")

		#Generate Table writer
		self.o("class %sOut(scalgoproto.TableOut):"%table.name)
		self.outputDoc(table, "\t")
		self.o("\t_MAGIC:typing.ClassVar[int]=0x%08x"%table.magic)				
		self.o("\tdef __init__(self, writer: scalgoproto.Writer, withHeader: bool) -> None:")
		self.o('\t\t"""Private constructor. Call factory methods on scalgoproto.Reader to construct instances"""')
		self.o("\t\tsuper().__init__(writer, withHeader, b\"%s\")"%(cescape(table.default)))
		for node in table.values:
			if node.t == NodeType.VALUE:
				assert isinstance(node, Value)
				self.generateValueOut(node)
			elif node.t == NodeType.VLUNION:
				assert isinstance(node, VLUnion)
				self.generateVLUnionOut(node)
			elif node.t == NodeType.VLBYTES:
				assert isinstance(node, VLBytes)
				self.generateVLBytesOut(node)
			elif node.t == NodeType.VLLIST:
				assert isinstance(node, VLList)
				self.generateVLListOut(node)
			elif node.t == NodeType.VLTEXT:
				assert isinstance(node,VLText)
				self.generateVLTextOut(node)
			else:
				assert(False)
		self.o("")

	def generateStruct(self, node:Struct):
		name = self.value(node.identifier)
		self.o("class %s(scalgoproto.StructType):"%name)
		self.o("\t_WIDTH: typing.ClassVar[int] = %d"%node.bytes)
		init = []
		copy = []
		write = []
		read = []
		for v in node.values:
			assert isinstance(v, Value)
			thing = ('','', '', 0, 0, "")
			n = self.value(v.identifier)
			tn = self.value(v.type)
			copy.append("self.%s = %s"%(n, n))
			if v.type.type in typeMap:
				ti = typeMap[v.type.type]
				if v.type.type in (TokenType.FLOAT32 , TokenType.FLOAT64):
					init.append("%s: %s = 0.0"%(n, ti.p))
				elif v.type.type == TokenType.BOOL:
					init.append("%s: %s = False"%(n, ti.p))
				else:
					init.append("%s: %s = 0"%(n, ti.p))
				write.append("writer._data[offset+%d:offset+%d] = struct.pack('<%s', ins.%s)"%(v.offset, v.offset+ti.w, ti.s, n))
				read.append("struct.unpack('<%s', reader._data[offset+%d:offset+%d])[0]"%(ti.s, v.offset, v.offset+ti.w))
			elif v.type.type == TokenType.IDENTIFIER and v.enum:
				init.append("%s: %s = %s(0)"%(n, tn, tn))
				write.append("writer._data[offset+%d] = int(ins.%s)"%(v.offset, n))
				read.append("%s(reader._data[offset+%d])"%(tn, v.offset))
			elif v.type.type == TokenType.IDENTIFIER and v.struct:
				init.append("%s: %s = %s()"%(n, tn, tn))
				write.append("%s._write(writer, offset+%d, ins.%s)"%(tn, v.offset, n))
				read.append("%s._read(reader, offset+%d)"%(tn, v.offset))
			else:
				assert(False)
		self.o("\tdef __init__(self, %s) -> None:"%(", ".join(init)))
		for line in copy:
			self.o("\t\t%s"%line)
		self.o("\t@staticmethod")
		self.o("\tdef _write(writer: scalgoproto.Writer, offset:int, ins: '%s') -> None:"%name)
		for line in write:
			self.o("\t\t%s"%line)
		self.o("\t@staticmethod")
		self.o("\tdef _read(reader: scalgoproto.Reader, offset:int) -> '%s':"%name)
		self.o("\t\treturn %s("%name)
		for line in read:
			self.o("\t\t\t%s,"%line)
		self.o("\t\t)")
		self.o()

	def generateEnum(self, node:Enum) -> None:
		name = self.value(node.identifier)
		self.o("class %s(enum.IntEnum):"%name)
		self.outputDoc(node, "\t")
		index = 0
		for ev in node.values:
			self.o("\t%s = %d"%(self.value(ev), index))
			index += 1
		self.o()

	def generate(self, ast: List[AstNode]) -> None:
		for node in ast:
			if node.t == NodeType.STRUCT:
				assert isinstance(node, Struct)
				self.generateStruct(node)
			elif node.t == NodeType.ENUM:
				assert isinstance(node, Enum)
				self.generateEnum(node)
			elif node.t == NodeType.TABLE:
				assert isinstance(node, Table)
				self.generateTable(node)

def run(args) -> int:
	data = open(args.schema, "r").read()
	p = Parser(data)
	out = open(args.output, "w")
	try:
		ast = p.parseDocument()
		if not annotate(data, ast):
			print("Invalid schema is valid")
			return 1
		g = Generator(data, out)
		print("# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-", file=out)
		print("# THIS FILE IS GENERATED DO NOT EDIT", file=out)
		print("import scalgoproto, enum, typing, struct, math", file=out)
		print("", file=out)
		g.generate(ast)
		return 0
	except ParseError as err:
		err.describe(data)
	return 1

def setup(subparsers) -> None:
	cmd = subparsers.add_parser('py', help='Generate python code')
	cmd.add_argument('schema', help='schema to generate things from')
	cmd.add_argument('output', help="where do we store the output")
	cmd.set_defaults(func=run)


