import sys
import os
from lexer import tokenize
from interpreter import Interpreter

def main():
    # Verifica se um nome de arquivo foi passado como argumento
    if len(sys.argv) > 1:
        program_file = sys.argv[1]
    else:
        # Se nenhum arquivo for passado, usa 'program.lqs' como padrão
        program_file = "program.lqs"

    if not os.path.exists(program_file):
        print(f"Erro: O arquivo '{program_file}' não foi encontrado.")
        return

    # Pega o diretório do arquivo principal para resolver importações
    base_dir = os.path.dirname(os.path.abspath(program_file))

    with open(program_file, "r", encoding='utf-8') as f:
        code = f.read()

    tokens = tokenize(code)
    # Passa o diretório para o interpretador
    interp = Interpreter(base_path=base_dir)
    interp.run(tokens)

if __name__ == "__main__":
    main()