# Squad Assistant

Português · [English](README.md)

Assistente open source e self-hosted para squads no **Slack** e no **Mattermost**.

- **Review assistants** acompanham os merge requests do GitLab publicados em um canal de review:
  marcam cada thread com um emoji de status (aguardando review, em revisão, resolvida/aprovada,
  mergeada, fechada), mencionam a squad de quem abriu a thread e publicam na thread o status dos
  pipelines e o aviso de merge.
- **Daily assistants** avisam a squad antes de cada daily, com horários por dia da semana e
  revezamento opcional do facilitador por dia ou por semana. O envio pode ser pelo bot ou por
  incoming webhook.

Você pode criar quantos assistants quiser, cada um com suas próprias configurações. A interface
e as mensagens do bot são multilíngues (inglês e português do Brasil, para começar).

## Início rápido

```bash
cp .env.example .env        # defina SQUAD_PUBLIC_URL, SQUAD_SECRET_KEY e SQUAD_ADMIN_PASSWORD
docker compose up -d        # SQLite, dados no volume "data"
```

Acesse http://localhost:8000. Para usar PostgreSQL, defina
`SQUAD_DATABASE_URL=postgresql+psycopg://...` e rode `docker compose --profile postgres up -d`.

## Configurando um review assistant

1. Crie uma **conexão** de Slack ou Mattermost (token do bot) e uma **conexão GitLab**
   (token com `read_api`).
2. Cadastre os **membros** (ID no chat e usuário do GitLab) e agrupe-os em **squads**.
3. Crie o review assistant: canal, projetos GitLab, squads, intervalo de varredura, emojis e ações.
   A interface mostra uma única vez a **URL do webhook e o secret token**. No GitLab, vá em
   *Settings → Webhooks* e marque os eventos *Merge request*, *Comments* e *Pipeline*.

O backend segue Clean Architecture (`domain`, `application`, `infrastructure` e `interfaces`),
descrita no [CLAUDE.md](CLAUDE.md).

A squad mencionada é a do autor: ele é identificado pelo usuário que postou a thread ou, se não
estiver cadastrado, pelo usuário do GitLab que abriu a MR. Na interface, **Threads** mostra as MRs
acompanhadas e **Testar** valida os tokens das conexões.

## Daily assistant

Configure os dias e horários, o fuso, os participantes na ordem do revezamento (marque quem estiver
ausente para pular), o revezamento por dia ou por semana, a antecedência do aviso e o envio pelo
bot ou por incoming webhook (Slack ou Mattermost).

## Banco de dados

SQLite por padrão ou PostgreSQL. As migrações (Alembic) rodam sozinhas ao iniciar o app.

Os detalhes de estados, permissões do bot e desenvolvimento estão no [README em inglês](README.md).

## Licença

[Apache License 2.0](LICENSE)
