import os
import importlib.util
from lexer import tokenize
import pyautogui
import requests

# --- Classes de Controle do Interpretador ---
class ReturnValue(Exception):
    """Exceção especial usada para controlar o fluxo de retorno das funções LQS."""
    def __init__(self, value):
        self.value = value

# --- Classes Embutidas ---
class HttpsRequests:
    """Classe para fazer requisições HTTP a partir da LogiqScript."""
    def __init__(self, url):
        self.url = url
        try:
            self._request = requests.get(url, timeout=10)
        except requests.exceptions.RequestException as e:
            raise IOError(f"Não foi possível conectar a '{url}': {e}")
    def json(self):
        try: return self._request.json()
        except requests.exceptions.JSONDecodeError: return None
    def text(self): return self._request.text
    def status(self): return self._request.status_code

class FileWrapper:
    """Classe para manipulação de arquivos."""
    def __init__(self, filename, mode):
        if mode not in ['r', 'w', 'a']: raise ValueError("Modo inválido. Use 'r', 'w', ou 'a'.")
        self._filename, self._mode, self._file = filename, mode, None
    def open_file(self, base_path):
        self._file = open(os.path.join(base_path, self._filename), self._mode, encoding='utf-8')
    def read(self):
        if not self._file or 'r' not in self._mode: raise IOError("Arquivo não aberto para leitura.")
        return self._file.read()
    def write(self, content):
        if not self._file or 'w' not in self._mode and 'a' not in self._mode: raise IOError("Arquivo não aberto para escrita.")
        return self._file.write(str(content))
    def close(self):
        if self._file: self._file.close()
    def __repr__(self):
        status = " (fechado)" if not self._file or self._file.closed else ""
        return f"<Arquivo: '{self._filename}', modo='{self._mode}'{status}>"

class InputManager:
    """Classe para controlar o mouse e o teclado."""
    def __init__(self): pass
    def move(self, x, y): pyautogui.moveTo(x, y, duration=0.25); return ""
    def click_left(self): pyautogui.leftClick(); return ""
    def click_right(self): pyautogui.rightClick(); return ""
    def write(self, text, interval_=0.05): pyautogui.write(text, interval=interval_); return ""
    def mouse_position(self): return list(pyautogui.position())

# --- Funções Embutidas ---
def builtin_len(obj):
    if isinstance(obj, (str, list, dict)): return len(obj)
    raise TypeError("Tipo de objeto inválido para len().")
def builtin_type(obj): return str(type(obj).__name__)
def builtin_append(lst, item):
    if not isinstance(lst, list): raise TypeError("append() só funciona com listas.")
    lst.append(item); return lst
def builtin_to_string(obj): return str(obj)
def builtin_to_number(obj):
    try: return float(obj)
    except (ValueError, TypeError): raise ValueError("Não foi possível converter para número.")

# --- O Interpretador ---
class Interpreter:
    def __init__(self, base_path='.'):
        self.base_path = base_path
        self.variables = {}
        self.functions = {
            'len': builtin_len, 'type': builtin_type, 'append': builtin_append,
            'to_string': builtin_to_string, 'to_number': builtin_to_number,
            'input': input, 'File': FileWrapper, 'InputManager': InputManager, 'Https': HttpsRequests
        }

    def run_lqs_function(self, func_def, args):
        param_names, body_tokens = func_def["params"], func_def["body"]
        old_vars = self.variables
        self.variables = old_vars.copy()
        self.variables.update(dict(zip(param_names, args)))
        return_val = None
        try:
            self.run(body_tokens)
        except ReturnValue as rv:
            return_val = rv.value
        self.variables = old_vars
        return return_val

    def parse_atom(self, tokens, i):
        tok_type, value = tokens[i]
        if tok_type == 'NUMBER':
            return (int(value) if '.' not in value else float(value)), i + 1
        if tok_type == 'STRING': return value.strip('"'), i + 1
        if tok_type == 'LBRACK': # Lista
            lst, i_new = [], i + 1
            if tokens[i_new][0] != 'RBRACK':
                while True:
                    val, i_new = self.eval_expr(tokens, i_new)
                    lst.append(val)
                    if i_new >= len(tokens) or tokens[i_new][0] == 'RBRACK': break
                    if tokens[i_new][0] == 'COMMA': i_new += 1
            return lst, i_new + 1
        if tok_type == 'LBRACE': # Dicionário
            dct, i_new = {}, i + 1
            if tokens[i_new][0] != 'RBRACE':
                while True:
                    key_val, i_new = self.eval_expr(tokens, i_new)
                    if tokens[i_new][0] != 'COLON': raise SyntaxError("Esperado ':' no dicionário.")
                    i_new += 1
                    val, i_new = self.eval_expr(tokens, i_new)
                    dct[key_val] = val
                    if i_new >= len(tokens) or tokens[i_new][0] == 'RBRACE': break
                    if tokens[i_new][0] == 'COMMA': i_new += 1
            return dct, i_new + 1
        if tok_type == 'LPAREN':
            val, i_new = self.eval_expr(tokens, i + 1)
            if i_new >= len(tokens) or tokens[i_new][0] != 'RPAREN': raise SyntaxError("Esperado ')'")
            return val, i_new + 1
        if tok_type == 'ID':
            if value in self.variables: return self.variables[value], i + 1
            if value in self.functions: return self.functions[value], i + 1
            raise NameError(f"Variável ou função '{value}' não definida.")
        raise SyntaxError(f"Token inesperado na expressão: {value}")
    
    def parse_call_access(self, tokens, i):
        left, i = self.parse_atom(tokens, i)
        while i < len(tokens):
            tok_type = tokens[i][0]
            if tok_type == 'LPAREN':
                args, i = [], i + 1
                if tokens[i][0] != 'RPAREN':
                    while True:
                        val, i_new = self.eval_expr(tokens, i); args.append(val); i = i_new
                        if i >= len(tokens) or tokens[i][0] == 'RPAREN': break
                        if tokens[i][0] == 'COMMA': i += 1
                i += 1
                if isinstance(left, dict) and "params" in left: left = self.run_lqs_function(left, args)
                elif callable(left):
                    if left == FileWrapper:
                        instance = left(*args); instance.open_file(self.base_path); left = instance
                    else: left = left(*args)
                else: raise TypeError(f"'{left}' não é uma função ou tipo chamável.")
                continue
            elif tok_type == 'DOT':
                i += 1; prop_name = tokens[i][1]; i += 1
                if i < len(tokens) and tokens[i][0] == 'LPAREN':
                    args, i = [], i + 1
                    if tokens[i][0] != 'RPAREN':
                        while True:
                            val, i_new = self.eval_expr(tokens, i); args.append(val); i = i_new
                            if i >= len(tokens) or tokens[i][0] == 'RPAREN': break
                            if tokens[i][0] == 'COMMA': i += 1
                    i += 1
                    method = getattr(left, prop_name, None)
                    if not method or not callable(method): raise AttributeError(f"Objeto não tem o método '{prop_name}'.")
                    left = method(*args)
                else:
                    left = getattr(left, prop_name, None)
                    if left is None: raise AttributeError(f"Objeto não tem o atributo '{prop_name}'.")
                continue
            elif tok_type == 'LBRACK':
                i += 1
                index_val, i = self.eval_expr(tokens, i)
                if tokens[i][0] != 'RBRACK': raise SyntaxError("Esperado ']' para fechar acesso.")
                i += 1
                try:
                    left = left[index_val]
                except (TypeError, KeyError, IndexError):
                    raise RuntimeError(f"Índice ou chave inválida '{index_val}'")
                continue
            else: break
        return left, i
    
    def eval_expr(self, tokens, i):
        left, i = self.parse_call_access(tokens, i)
        while i < len(tokens):
            tok_type = tokens[i][0]
            # CORREÇÃO PRINCIPAL AQUI: Adicionados GTE (>=) e LTE (<=)
            if tok_type in ('PLUS', 'MINUS', 'MUL', 'DIV', 'GT', 'LT', 'GTE', 'LTE', 'EQEQ', 'NEQ'):
                op, (right, i) = tokens[i][1], self.parse_call_access(tokens, i + 1)
                left = eval(f'a {op} b', {'a': left, 'b': right})
                continue
            else: break
        return left, i

    def get_block(self, tokens, start_index, terminators=("END",)):
        block, nesting_level, i = [], 1, start_index
        openers = ("IF", "WHILE", "FOR", "FUNC", "TRY")
        while i < len(tokens):
            tok_type, _ = tokens[i]
            if tok_type in openers: nesting_level += 1
            elif tok_type in terminators or (tok_type == "END" and "END" in terminators):
                nesting_level -= 1
                if nesting_level == 0: return block, i
            block.append(tokens[i]); i += 1
        raise SyntaxError(f"Bloco de código não foi fechado corretamente com um de: {terminators}")

    def run(self, tokens):
        i = 0
        while i < len(tokens):
            if i >= len(tokens): break
            token, value = tokens[i]

            if token == "LET":
                var_name = tokens[i+1][1]; i += 3
                val, i = self.eval_expr(tokens, i); self.variables[var_name] = val
                continue
            
            elif token == "IF":
                cond_val, cond_end_idx = self.eval_expr(tokens, i + 1)
                if_block, mid_idx = self.get_block(tokens, cond_end_idx, terminators=("ELSE", "END"))
                else_block, end_idx = [], mid_idx
                if mid_idx < len(tokens) and tokens[mid_idx][0] == "ELSE":
                    else_block, end_idx = self.get_block(tokens, mid_idx + 1, terminators=("END",))
                if cond_val: self.run(if_block)
                elif else_block: self.run(else_block)
                i = end_idx + 1
                continue
            
            elif token == "FUNC":
                func_name = tokens[i+1][1]; i += 2
                params = []
                if tokens[i][0] == "LPAREN":
                    i += 1
                    while tokens[i][0] != "RPAREN":
                        if tokens[i][0] == "ID": params.append(tokens[i][1])
                        i += 1
                    i += 1
                body, end_idx = self.get_block(tokens, i)
                self.functions[func_name] = {"params": params, "body": body}
                i = end_idx + 1
                continue
            
            elif token == "WHILE":
                cond_start_idx = i + 1
                _, cond_end_idx = self.eval_expr(tokens, cond_start_idx)
                body, end_idx = self.get_block(tokens, cond_end_idx)
                while self.eval_expr(tokens, cond_start_idx)[0]:
                    try:
                        self.run(body)
                    except ReturnValue:
                        break 
                i = end_idx + 1
                continue

            elif token == "TRY":
                try_block, mid_idx = self.get_block(tokens, i + 1, terminators=("CATCH", "END"))
                catch_block, end_idx = [], mid_idx
                if mid_idx < len(tokens) and tokens[mid_idx][0] == "CATCH":
                    catch_block, end_idx = self.get_block(tokens, mid_idx + 1, terminators=("END",))
                try: self.run(try_block)
                except Exception:
                    if catch_block: self.run(catch_block)
                i = end_idx + 1
                continue
            
            elif token == "RETURN":
                val, i_new = self.eval_expr(tokens, i + 1)
                raise ReturnValue(val)

            elif token == "PRINT":
                val, i = self.eval_expr(tokens, i + 1); print(val)
                continue

            elif token == "ID" and i + 1 < len(tokens) and (tokens[i+1][0] == 'DOT' or tokens[i+1][0] == 'LPAREN'):
                _, i = self.eval_expr(tokens, i)
                continue
            else:
                i += 1
