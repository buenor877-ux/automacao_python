import argparse
import os
import subprocess
import sys

PASTA = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Sistema de controle de estoque")
    parser.add_argument(
        "--rotina", action="store_true",
        help="roda a rotina diária (backup + planilha) sem abrir a interface"
    )

    if parser.parse_args().rotina:
        # Modo usado pelo Agendador de Tarefas do Windows
        sys.path.insert(0, PASTA)
        import automacoes
        import banco

        automacoes.configurar_log()
        banco.inicializar_banco()
        for arquivo in automacoes.rotina_diaria():
            print(f"Gerado: {arquivo}")
    else:
        # Abre a interface no navegador
        subprocess.run([sys.executable, "-m", "streamlit", "run", os.path.join(PASTA, "app.py")])


if __name__ == "__main__":
    main()
