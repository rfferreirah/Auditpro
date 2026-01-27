# Compartilhando a Aplicação Localmente (ngrok)

Se você deseja mostrar o **Audit PRO** para outras pessoas via internet sem fazer um deploy completo em um servidor, você pode usar ferramentas de "túnel" como o **ngrok**.

## Usando o ngrok

O ngrok cria uma URL pública segura (https) que redireciona para o seu servidor local.

### 1. Instalação
Baixe e instale o ngrok em [ngrok.com/download](https://ngrok.com/download).

### 2. Autenticação
Crie uma conta no site do ngrok e configure seu token (comando disponível no dashboard do ngrok):
```powershell
ngrok config add-authtoken SEU_TOKEN_AQUI
```

### 3. Iniciando o Túnel
Com sua aplicação rodando localmente na porta 5000 (seja via `python run_prod.py` ou `flask`), abra um **novo terminal** e execute:

```powershell
ngrok http 5000
```

### 4. Compartilhando
O ngrok exibirá uma saída como esta:

```
Forwarding                    https://a1b2-c3d4.ngrok-free.app -> http://localhost:5000
```

Copie o link `https://...ngrok-free.app` e envie para quem você quiser. Eles terão acesso à sua aplicação como se estivessem no seu computador.

> **⚠️ Atenção:** 
> - A URL expira após algumas horas no plano gratuito.
> - Qualquer pessoa com o link terá acesso ao sistema e aos dados do REDCap configurados. Compartilhe com cuidado.
