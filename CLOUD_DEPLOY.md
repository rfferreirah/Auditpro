# Guia de Deploy na Nuvem (Render / Railway)

Este guia explica como colocar sua aplicação no ar gratuitamente (ou com baixo custo) usando **Render** ou **Railway**. Ambos são excelentes opções que se conectam direto ao seu GitHub.

## Pré-requisitos
1.  Ter o código do projeto em um repositório no **GitHub**.
2.  Ter o arquivo `Procfile` na raiz do projeto (já criado).
3.  Ter o `requirements.txt` com `gunicorn` (já atualizado).

---

## Opção 1: Deploy no Render (Grátis*)

O Render tem um plano gratuito para serviços web que dormem após inatividade.

1.  Crie uma conta em [render.com](https://render.com).
2.  Clique em **"New +"** e selecione **"Web Service"**.
3.  Conecte sua conta do GitHub e selecione o repositório deste projeto.
4.  Preencha os campos:
    *   **Name:** `audit-pro` (ou o nome que preferir)
    *   **Region:** Escolha a mais próxima (ex: Ohio ou Frankfurt)
    *   **Branch:** `main` (ou a branch que você está usando)
    *   **Runtime:** `Python 3`
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `gunicorn web_app:app`
5.  **Variáveis de Ambiente (Environment Variables):**
    Clique em "Advanced" ou role até "Environment Variables" e adicione:
    *   `REDCAP_API_URL`: (Sua URL do REDCap)
    *   `REDCAP_API_TOKEN`: (Seu Token)
    *   `SUPABASE_URL`: (Sua URL do projeto Supabase)
    *   `SUPABASE_KEY`: (Sua chave anon public do Supabase)
    *   `ANTHROPIC_API_KEY`: (Sua chave da Anthropic/Claude - Opcional)
    *   `PYTHON_VERSION`: `3.10.0` (Opcional, mas recomendado)
6.  Clique em **"Create Web Service"**.

O deploy vai começar. Pode levar alguns minutos. Quando terminar, você verá sua URL (ex: `https://audit-pro.onrender.com`).

---

## Opção 2: Deploy no Railway

O Railway é muito simples e robusto, geralmente pago (trial de $5), mas a experiência é excelente.

1.  Crie uma conta em [railway.app](https://railway.app).
2.  Clique em **"New Project"** -> **"Deploy from GitHub repo"**.
3.  Selecione seu repositório.
4.  Clique no projeto criado e vá em **"Variables"**.
5.  Adicione as variáveis do seu `.env`:
    *   `REDCAP_API_URL`
    *   `REDCAP_API_TOKEN`
    *   `SUPABASE_URL`
    *   `SUPABASE_KEY`
    *   `ANTHROPIC_API_KEY` (Opcional)
6.  Vá em **"Settings"** -> **"Generate Domain"** para criar uma URL pública.
7.  O Railway detectará automaticamente o `Procfile` e fará o deploy.

---

## Dicas Importantes para Nuvem

*   **HTTPS:** Tanto Render quanto Railway configuram HTTPS automaticamente para você.
*   **Dados Sensíveis:** NUNCA suba seu arquivo `.env` para o GitHub. Sempre configure as chaves (URL e Token) painel de administração da plataforma (seção "Environment Variables").
*   **Persistência:** Em planos gratuitos/básicos, arquivos criados no disco (como os PDFs gerados na pasta `outputs/`) podem ser apagados quando o servidor reinicia. Se precisar guardar os relatórios permanentemente, seria necessário configurar um armazenamento externo (como AWS S3), mas para uso pontual (gerar e baixar na hora), funciona perfeitamente.
