# Guia de Deploy - REDCap Data Quality Intelligence Agent

Este guia descreve os passos para instalar e executar a aplicação em um ambiente de produção Windows.

## Pré-requisitos

- Python 3.10 ou superior
- Acesso à internet (para instalar dependências)
- Token de API do REDCap

## Instalação

1.  **Clone ou baixe o repositório** para o servidor.
2.  **Abra o PowerShell** na pasta do projeto.
3.  **Crie um ambiente virtual** (recomendado):
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate
    ```
4.  **Instale as dependências**:
    ```powershell
    pip install -r requirements.txt
    ```

## Configuração

1.  Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como base, se houver, ou crie do zero):
    ```env
    REDCAP_API_URL=https://redcap.seu-instituicao.org/api/
    REDCAP_API_TOKEN=SEU_TOKEN_AQUI
    DEBUG=False
    ```
    > **Nota:** Em produção, certifique-se de que `DEBUG` está definido como `False`.

## Execução em Produção (Windows)

Para executar a aplicação de forma robusta e segura, utilizaremos o servidor `waitress` (já incluído nas dependências).

1.  **Execute o servidor**:
    ```powershell
    waitress-serve --port=5000 --call web_app:app
    ```
    
    Ou, se preferir usar o script Python:
    ```powershell
    python run_prod.py
    ```
    *(Crie o arquivo `run_prod.py` com o conteúdo abaixo se não existir)*:
    ```python
    from waitress import serve
    from web_app import app
    
    if __name__ == "__main__":
        print("Iniciando servidor de produção na porta 5000...")
        serve(app, host='0.0.0.0', port=5000)
    ```

2.  Acesse `http://localhost:5000` (ou o IP do servidor) no navegador.

## Manutenção

- **Logs:** Acompanhe a saída do terminal para verificar logs de erro.
- **Reiniciar:** Se fizer alterações no código ou no `.env`, pare o processo (Ctrl+C) e inicie novamente.
