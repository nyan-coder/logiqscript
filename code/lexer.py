import re

TOKEN_SPEC = [
    # --- Tipos de Dados e Estruturas ---
    ("NUMBER",   r"\d+(\.\d*)?"),
    ("STRING",   r'"[^"]*"'),
    ("LBRACK",   r"\["), 
    ("RBRACK",   r"\]"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("COLON",    r":"),
    ("DOT",      r"\."),

    # --- Palavras-chave ---
    ("COMMENT",  r'#.*'),
    ("IMPORT",   r'import'),
    ("LET",      r"let"),
    ("PRINT",    r"print"),
    ("IF",       r"if"),
    ("ELSE",     r"else"),
    ("WHILE",    r"while"),
    ("FOR",      r"for"),
    ("IN",       r"in"),
    ("END",      r"end"),
    ("FUNC",     r"func"),
    ("RETURN",   r"return"),
    ("TRY",      r"try"),
    ("CATCH",    r"catch"),
    ("INPUT",    r"input"),
    ("ID",       r"[a-zA-Z_]\w*"),

    # --- Operadores e outros (ORDEM CORRIGIDA) ---
    ("EQEQ",     r"=="),
    ("NEQ",      r"!="),
    ("GTE",      r">="),
    ("LTE",      r"<="),
    ("EQ",       r"="),
    ("GT",       r">"),
    ("LT",       r"<"),
    ("PLUS",     r"\+"),
    ("MINUS",    r"-"),
    ("MUL",      r"\*"),
    ("DIV",      r"/"),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("COMMA",    r","),
    ("NEWLINE",  r"\n"),
    ("SKIP",     r"[ \t]+"),
    ("MISMATCH", r"."),
]


token_re = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

def tokenize(code):
    tokens = []
    for match in token_re.finditer(code):
        kind = match.lastgroup
        value = match.group()
        if kind in ("SKIP", "NEWLINE", "COMMENT"):
            continue
        elif kind == "MISMATCH":
            raise SyntaxError(f"Token inválido: {value}")
        tokens.append((kind, value))
    return tokens
