# Design tokens — referência `financas` (Spendly)

> Documento gerado no **Passo 0** da tarefa de redesenho do frontend do CRM.
> Nenhum arquivo do CRM foi alterado além deste documento.

## 0. Metadados da extração

| Item | Valor |
|---|---|
| Repositório de referência | `https://github.com/BRUNOTGTH19/financas` |
| Clone local | `C:\Users\Bruno\Desktop\projetos\financas-ref` |
| Commit analisado | `70d4add` — `ci(deploy): publica aplicacao no github pages` |
| Data da extração | 2026-11-07 |
| Stack da referência | React 18 + Vite + TypeScript + Tailwind 3 + Zustand + React Router 7 |
| Tailwind | `darkMode: 'class'`, `content: ['./index.html', './src/**/*.{ts,tsx}']` |
| Licença | Sem arquivo `LICENSE`. **Não reutilizar código literal**; apenas os tokens abaixo. |

### Arquivos lidos (fonte dos tokens)

- `tailwind.config.js` — cores, fonte, sombras, raio `4xl`, keyframes/animações.
- `src/index.css` — variáveis CSS, gradientes, classes de componente, overrides de dark.
- `index.html` — fontes, `theme-color`, script anti-flash de tema, `color-scheme`.
- `src/components/AppShell.tsx` — grid do shell, sidebar, header sticky, bottom nav.
- `src/components/Brand.tsx`, `Badge.tsx`, `Modal.tsx`, `ConfirmDialog.tsx`, `PageHeader.tsx`, `ProgressBar.tsx`, `EmptyState.tsx`, `ThemeSelector.tsx`, `MonthSwitcher.tsx`.
- `src/pages/DashboardPage.tsx`, `WeeksPage.tsx`, `SettingsPage.tsx` — padrões de card, alerta, grid e espaçamento.
- `src/theme/theme.ts` e `ThemeProvider.tsx` — chave de storage e resolução claro/escuro/sistema.

### O que **não** foi usado

- Pasta `vault/` — contém documentação interna (inclui `09 - Design Tokens.md`) e um `app.json`. **Não lida, não copiada e não usada**, conforme a restrição da tarefa.
- Pasta `obsidian-vault/` — notas internas. Não usada.
- Nenhum `.env`, credencial, chave ou dado de produção foi aberto. Nada sensível foi encontrado nos arquivos de estilo analisados.

---

## 1. Paleta

### 1.1 Cores semânticas de base (RGB em variáveis CSS)

Definidas em `src/index.css` como triplas RGB para permitir opacidade (`rgb(var(--x) / <alpha-value>)`) no Tailwind.

| Token | Variável CSS | Claro (RGB) | Claro (hex) | Escuro (RGB) | Escuro (hex) | Origem |
|---|---|---|---|---|---|---|
| Fundo da página | `--color-cream` | `245 242 234` | `#F5F2EA` | `8 16 12` | `#08100C` | `index.css` `:root` / `.dark` |
| Superfície (cards) | `--color-paper` | `252 251 247` | `#FCFBF7` | `16 28 21` | `#101C15` | `index.css` `:root` / `.dark` |
| Texto | `--color-ink` | `20 33 26` | `#14211A` | `232 241 234` | `#E8F1EA` | `index.css` `:root` / `.dark` |
| `color-scheme` | — | `light` | — | `dark` | — | `index.css` |

Mapeamento Tailwind (`tailwind.config.js`):

```js
cream: 'rgb(var(--color-cream) / <alpha-value>)'
paper: 'rgb(var(--color-paper) / <alpha-value>)'
ink:   'rgb(var(--color-ink)   / <alpha-value>)'
```

### 1.2 Escala `brand` (verde)

Definida literalmente em `tailwind.config.js`.

| Token | Hex | Uso observado |
|---|---|---|
| `brand-50` | `#F1F8F2` | fundo de badge "ok", hover suave, ícones de empty state |
| `brand-100` | `#DCF0E2` | track de progresso, botão primário no dark |
| `brand-200` | `#BCE3C6` | hover do primário no dark |
| `brand-300` | `#8DCE9F` | texto/links no dark, ícones |
| `brand-400` | `#57B176` | texto em badges no dark |
| `brand-500` | `#348F57` | **foco** (`ring-brand-500`), borda de campo em foco, fill de progresso |
| `brand-600` | `#247345` | eyebrow (`text-brand-600`) |
| `brand-700` | `#1E5B39` | links e textos de ação no claro |
| `brand-800` | `#1A4930` | — |
| `brand-900` | `#163C29` | hover do primário, card promocional da sidebar |
| `brand-950` | `#0B2117` | botão primário, nav ativa, card de destaque, overlay do modal |

### 1.3 Destaque `lime`

| Token | Hex | Uso observado |
|---|---|---|
| `lime` | `#D8F36B` | CTA secundário (`.btn-lime`), item ativo da bottom nav, seleção de texto, detalhes no dark |
| `lime` hover | `#C9EB52` | hover de `.btn-lime` (valor hard-coded `hover:bg-[#c9eb52]` no `index.css`) |

`lime` também aparece com opacidade: `bg-lime/60`, `bg-lime/70`, `bg-lime/15`, `bg-lime/10`, `bg-lime/20`, `bg-lime/30`.

### 1.4 Cores de estado (paleta padrão do Tailwind)

A referência **não** cria tokens próprios de sucesso/erro/atenção; usa a paleta padrão do Tailwind via classes.

| Papel | Claro | Escuro | Onde |
|---|---|---|---|
| Sucesso / ok | `bg-brand-50 text-brand-700` | `bg-brand-400/15 text-brand-200` | `Badge.tsx` tom `ok` |
| Atenção | `bg-amber-50 text-amber-700` | `bg-amber-400/15 text-amber-200` | `Badge.tsx` tom `attention` |
| Erro / estouro | `bg-rose-50 text-rose-700` | `bg-rose-400/15 text-rose-200` | `Badge.tsx` tom `over`, `.btn-danger`, `.error-text` |
| Informação | `bg-sky-50 text-sky-700` | `bg-sky-400/15 text-sky-200` | `Badge.tsx` tom `info` |
| Neutro | `bg-ink/5 text-ink/50` | idem (ink inverte) | `Badge.tsx` tom `neutral` |
| Destaque | `bg-lime/60 text-brand-950` | `bg-lime text-brand-950` | `Badge.tsx` tom `lime` |

Valores hex dos tons usados (Tailwind v3 padrão):

| Classe | Hex |
|---|---|
| `amber-50` / `amber-700` | `#FFFBEB` / `#B45309` |
| `rose-50` / `rose-700` | `#FFF1F2` / `#BE123C` |
| `sky-50` / `sky-700` | `#F0F9FF` / `#0369A1` |
| `rose-600` (erro em texto) | `#E11D48` |
| `sky-900` (CTA do alerta) | `#0C4A6E` |

### 1.5 Bordas, overlays e superfícies translúcidas

| Uso | Classe | Efeito |
|---|---|---|
| Borda de card | `border-ink/[0.06]` | ~6% de ink sobre paper |
| Borda de card no dark | `dark:border-white/[0.08]` | 8% branco |
| Borda de campo | `border-ink/10` | 10% |
| Borda de campo no dark | `dark:border-white/10` | 10% |
| Borda do header | `border-ink/[0.05]` | 5% |
| Superfície do header | `bg-cream/85 backdrop-blur-md` | vidro |
| Superfície da sidebar | `bg-cream/60 backdrop-blur` | vidro |
| Superfície da bottom nav | `bg-paper/95 backdrop-blur-md` | vidro |
| Overlay de modal | `bg-brand-950/40 backdrop-blur-sm` | claro |
| Overlay de modal (dark) | `dark:bg-black/60` | escuro |
| Botão fantasma | `bg-white/60`, hover `bg-white` | claro |
| Botão fantasma (dark) | `dark:bg-white/5`, hover `white/10` | escuro |
| Ícone em botão | `bg-white/70`, `text-ink/60` | claro |

### 1.6 Gradientes de fundo

Aplicados no `body` (`index.css`), fixos ao scroll:

```css
/* claro */
background-image:
  radial-gradient(circle at 12% -10%, rgba(216, 243, 107, 0.35), transparent 34rem),
  radial-gradient(circle at 92% 4%,  rgba(52, 143, 87, 0.1),  transparent 26rem);

/* escuro */
background-image:
  radial-gradient(circle at 12% -10%, rgba(216, 243, 107, 0.09), transparent 34rem),
  radial-gradient(circle at 92% 4%,  rgba(52, 143, 87, 0.2),  transparent 26rem);
```

- `216,243,107` = `lime` em RGB.
- `52,143,87` = `brand-500` em RGB.
- `background-attachment: fixed`.

Card de destaque do dashboard: `bg-brand-950 text-white shadow-float` com halo `bg-lime/10 blur-3xl` (`h-48 w-48`, `-right-16 -top-20`).

---

## 2. Tipografia

| Item | Valor | Origem |
|---|---|---|
| Família | `"Plus Jakarta Sans"`, `ui-sans-serif`, `system-ui`, `sans-serif` | `tailwind.config.js` |
| Carregamento | Google Fonts, pesos `400;500;600;700;800` + itálico `400`, `display=swap` | `index.html` |
| Base do `body` | `font-sans`, `antialiased` | `index.css` |

### Escala observada

| Papel | Classes | Tamanho aprox. | Peso | Tracking |
|---|---|---|---|---|
| Título de página (h1) | `text-3xl sm:text-4xl font-extrabold tracking-[-0.03em]` | 30 → 36px | 800 | -0.03em |
| Título de modal | `text-xl font-extrabold tracking-tight` | 20px | 800 | tight |
| Título de seção | `text-lg font-extrabold tracking-tight` (`.section-title`) | 18px | 800 | tight |
| Texto de card em destaque | `text-sm font-extrabold leading-snug` | 14px | 800 | — |
| Corpo | `text-sm` / `text-[15px]` / `text-[13px]` | 13–15px | 400–700 | — |
| Descrição de página | `text-sm sm:text-[15px] leading-relaxed text-ink/55` | 14 → 15px | 400 | — |
| Eyebrow | `text-[11px] font-extrabold uppercase tracking-[0.18em] text-brand-600` | 11px | 800 | 0.18em |
| Label de campo (`.label`) | `text-xs font-bold uppercase tracking-[0.12em]` | 12px | 700 | 0.12em |
| Micro-label de card | `text-[11px] font-extrabold uppercase tracking-[0.16em]` | 11px | 800 | 0.16em |
| Badge/chip (`.chip`) | `text-[11px] font-bold` | 11px | 700 | — |
| Bottom nav | `text-[10px] font-bold` | 10px | 700 | — |
| Botão | `text-sm font-bold` (`.btn`), `.btn-sm` = `text-xs` | 14px / 12px | 700 | — |
| Marca | `text-[17px] font-extrabold tracking-[-0.02em]` | 17px | 800 | -0.02em |
| Subtítulo da marca | `text-[10px] font-bold uppercase tracking-[0.16em]` | 10px | 700 | 0.16em |

Números monetários usam `.money` = `tabular-nums`.

---

## 3. Raios, sombras e espaçamentos

### 3.1 Raios

| Token/classe | Valor | Uso |
|---|---|---|
| `rounded-full` | 9999px | botões, chips, navegação de mês, bottom nav |
| `rounded-xl` | 0.75rem (12px) | ícone dentro de card, skeleton |
| `rounded-2xl` | 1rem (16px) | campos, nav items, ícones de alerta, botões de tema |
| `rounded-3xl` | 1.5rem (24px) | cards, sidebar promo |
| `rounded-4xl` | 2rem (32px) | modal (token novo no `tailwind.config.js`) |
| `rounded-t-4xl` | 2rem no topo | modal em mobile (bottom sheet) |

### 3.2 Sombras

```js
card:  '0 1px 2px rgba(20, 33, 26, 0.04), 0 12px 32px -20px rgba(20, 33, 26, 0.28)'
float: '0 24px 60px -30px rgba(11, 33, 23, 0.55)'
```

- `shadow-card` em cards e nav ativa no claro.
- `shadow-float` no card de destaque e no modal.
- `shadow-sm` em botões de ícone e no logo.
- No dark: cards usam `dark:shadow-none` (a separação é feita por borda).

### 3.3 Espaçamentos e containers

| Contexto | Valores |
|---|---|
| Container principal | `mx-auto w-full max-w-5xl px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-16 lg:pt-10` |
| Sidebar | largura `17.5rem`; `px-5 py-7`; item `px-3.5 py-3`; `space-y-1.5`; `mt-10` |
| Header | `px-4 py-3 sm:px-6 lg:px-10 lg:py-4`; `sticky top-0 z-30` |
| Card | `.card` + `.card-pad` = `p-5 sm:p-6` |
| Pilha de página | `space-y-6` |
| Grids de dashboard | `gap-3`; colunas `lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]` |
| Grid do shell | `lg:grid lg:grid-cols-[17.5rem_minmax(0,1fr)]` |
| Bottom nav | `grid grid-cols-5 px-1.5 py-1.5`, `safe-bottom` |
| Modal | `p-5 sm:p-7`, `max-h-[92vh]`, `sm:max-w-lg`, `sm:p-6` no overlay |
| Ritmo interno de card | `mt-1`, `mt-1.5`, `mt-2`, `mt-3`, `mt-4`, `mt-5` |

---

## 4. Componentes base (contratos visuais)

Reimplementar com os mesmos tokens, **sem copiar o código-fonte**.

| Classe | Definição visual |
|---|---|
| `.card` | `rounded-3xl border border-ink/[0.06] bg-paper shadow-card dark:border-white/[0.08] dark:shadow-none` |
| `.card-pad` | `p-5 sm:p-6` |
| `.btn` | `inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-bold transition duration-150 ease-out active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50` |
| `.btn-primary` | fundo `brand-950`, texto branco; dark: fundo `brand-100`, texto `brand-950` |
| `.btn-lime` | fundo `lime`, texto `brand-950`, hover `#C9EB52` |
| `.btn-ghost` | borda `ink/10`, fundo `white/60`, hover `white`; dark: `white/10` + `white/5` |
| `.btn-danger` | `bg-rose-50 text-rose-700`, hover `rose-100`; dark `rose-950/60` + `rose-200` |
| `.btn-sm` | `px-3.5 py-2 text-xs` |
| `.icon-btn` | `h-9 w-9 rounded-full border bg-white/70 text-ink/60`, hover borda `ink/20` |
| `.label` | `mb-1.5 block text-xs font-bold uppercase tracking-[0.12em] text-ink/50` |
| `.field` | `w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-semibold placeholder:font-normal placeholder:text-ink/30 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20` |
| `.hint` | `text-xs leading-relaxed text-ink/50` |
| `.error-text` | `mt-1.5 text-xs font-semibold text-rose-600 dark:text-rose-300` |
| `.chip` | `inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold` |
| `.section-title` | `text-lg font-extrabold tracking-tight text-ink` |
| `.money` | `tabular-nums` |
| `.link-underline` | `font-bold text-brand-700 underline decoration-brand-300 decoration-2 underline-offset-4` |
| `.skeleton` | `animate-pulse rounded-xl bg-ink/5` |

### Foco e seleção

```css
:focus-visible { outline: none; ring-2; ring-brand-500; ring-offset-2; ring-offset-cream; }
::selection   { background: lime; color: brand-950; }
```

### Texto secundário (opacidades)

A referência usa a escala de opacidade do `ink`: `/15`, `/20`, `/25`, `/30`, `/35`, `/40`, `/45`, `/50`, `/55`, `/60`. No dark há overrides para manter legibilidade (`index.css` linhas 150–172):

| Classe no dark | Opacidade efetiva |
|---|---|
| `text-ink/20`, `/25`, `/30` | `0.55` |
| `text-ink/35`, `/40`, `/45` | `0.68` |
| `text-ink/50`, `/55`, `/60` | `0.80` |
| `text-white/45`, `/55` | `0.68` |

> ⚠️ Ver seção 7: no **claro**, `text-ink/50` e `/55` não atingem WCAG AA para texto pequeno.

---

## 5. Animações e movimento

| Nome | Definição | Onde é usada |
|---|---|---|
| `fade-up` | `0% { opacity: 0; transform: translateY(8px) }` → `100% { opacity: 1; transform: translateY(0) }`, `0.35s ease-out both` | Entrada de página (`animate-fade-up` no wrapper de `DashboardPage`, `WeeksPage`, `ExpensesPage`, `FixedExpensesPage`, `SettingsPage`, `PlaceholderPage`) e painel de `Modal` |
| Transição padrão | `transition` (150ms, `cubic-bezier(0.4, 0, 0.2, 1)`) | botões, links, nav, ícones, cards clicáveis, campos |
| Botão pressionado | `active:scale-[0.98]` com `duration-150 ease-out` | `.btn` |
| Barra de progresso | `transition-all duration-500` na largura do fill | `ProgressBar.tsx` |
| Skeleton | `animate-pulse` | `.skeleton` |
| Hover de logo | `group-hover:bg-brand-900` (claro) / `dark:group-hover:bg-lime/90` | `Brand.tsx` |
| Halo decorativo | `blur-3xl` estático, sem animação | card de destaque |
| `framer-motion` | **não usado** | — |

### `prefers-reduced-motion`

**Não há tratamento na referência.** Este é um ponto a corrigir na reimplementação do CRM:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 6. Layout e breakpoints

Tailwind usa os breakpoints padrão. A referência só utiliza `sm` e `lg` de forma relevante.

| Breakpoint | Largura | Comportamento |
|---|---|---|
| base (mobile) | < 640px | Shell de coluna única; header sticky com marca compacta + trocador de mês; **bottom nav fixa** (`grid-cols-5`); `main` com `px-4`, `pb-28` (espaço para a nav); modal como bottom sheet (`items-end`, `rounded-t-4xl`) |
| `sm` | ≥ 640px | Paddings maiores (`sm:px-6`), títulos `text-4xl`, header de página em linha (`sm:flex-row sm:items-end sm:justify-between`), modal centralizado (`sm:items-center sm:p-6`, `sm:max-w-lg`, `sm:rounded-4xl`) |
| `md` | ≥ 768px | Sem uso explícito |
| `lg` | ≥ 1024px | Vira grid com **sidebar fixa** de `17.5rem` (`lg:sticky lg:top-0 lg:h-screen lg:flex lg:flex-col`); bottom nav some (`lg:hidden`); marca compacta some (`lg:hidden`); eyebrow do header aparece (`lg:block`); `main` com `lg:px-10 lg:pt-10 lg:pb-16` |
| `xl` | ≥ 1280px | Sem uso explícito (container limitado por `max-w-5xl`) |

### Estrutura do shell

```
div.min-h-screen.lg:grid.lg:grid-cols-[17.5rem_minmax(0,1fr)]
├── aside (sidebar, somente lg+)
└── div.min-w-0
    ├── header.sticky.top-0.z-30 (marca compacta / eyebrow + trocador de mês)
    ├── main.mx-auto.max-w-5xl (Outlet)
    └── nav.fixed.inset-x-0.bottom-0.z-40 (somente < lg)
```

Camadas (`z-index`): header `z-30`, bottom nav `z-40`, modal `z-50`.

### Safe areas

- `.safe-bottom` = `padding-bottom: env(safe-area-inset-bottom)` na bottom nav.
- Modal mobile encosta no rodapé (`items-end`, `p-0`).

---

## 7. Tema claro e escuro

| Item | Valor |
|---|---|
| Estratégia | `darkMode: 'class'` — classe `.dark` no `<html>` |
| Padrão | Claro, salvo preferência salva |
| Preferências | `light` \| `dark` \| `system` |
| Chave de storage | `fin:theme` (no CRM, usar chave própria, ex.: `crm:theme`) |
| Media query | `(prefers-color-scheme: dark)` |
| Aplicação | `applyTheme` adiciona/remove `.dark` e ajusta `style.colorScheme` |
| Anti-flash | Script inline no `<head>` do `index.html` lê o storage e aplica `.dark` antes do React montar |
| `theme-color` claro | `#F5F2EA` (`media="(prefers-color-scheme: light)"`) |
| `theme-color` escuro | `#08100C` (`media="(prefers-color-scheme: dark)"`) |
| `color-scheme` | `<meta name="color-scheme" content="light dark">` |

### Regras de inversão

- No dark, o papel do `ink` e do `cream` se inverte por variável CSS — não é necessário reescrever cada componente.
- Cards no dark trocam sombra por borda (`dark:border-white/[0.08] dark:shadow-none`).
- Botão primário inverte: `brand-950` → `brand-100`; nav ativa vira `lime` com texto `brand-950`.
- Overlays escurecem mais no dark (`bg-brand-950/40` → `dark:bg-black/60`).

---

## 8. Contraste (WCAG 2.1) — pares calculados

Cálculo de luminância relativa sobre os hex reais da referência.

| Par | Contraste | AA texto normal (4.5:1) | AA texto grande (3:1) |
|---|---|---|---|
| `ink` `#14211A` sobre `cream` `#F5F2EA` | **14.87:1** | ✅ | ✅ |
| `ink` sobre `paper` `#FCFBF7` | **16.07:1** | ✅ | ✅ |
| branco sobre `brand-950` | **16.88:1** | ✅ | ✅ |
| branco sobre `brand-900` | **12.26:1** | ✅ | ✅ |
| `brand-950` sobre `lime` | **13.63:1** | ✅ | ✅ |
| `brand-700` sobre `brand-50` | **7.45:1** | ✅ | ✅ |
| `rose-700` sobre `rose-50` | **5.72:1** | ✅ | ✅ |
| `sky-700` sobre `sky-50` | **5.57:1** | ✅ | ✅ |
| `amber-700` sobre `amber-50` | **4.84:1** | ✅ | ✅ |
| `ink` dark `#E8F1EA` sobre `cream` dark `#08100C` | **16.70:1** | ✅ | ✅ |
| `ink` dark sobre `paper` dark `#101C15` | **15.18:1** | ✅ | ✅ |
| `text-ink/60` sobre `cream` claro | **4.24:1** | ❌ | ✅ |
| `text-ink/55` sobre `cream` claro | **3.67:1** | ❌ | ✅ |
| `text-ink/50` sobre `cream` claro | **3.16:1** | ❌ | ✅ |
| `text-ink/40` sobre `cream` claro | **2.43:1** | ❌ | ❌ |
| `text-ink/35` sobre `cream` claro | **2.13:1** | ❌ | ❌ |
| `text-ink/55` sobre `cream` dark | **5.56:1** | ✅ | ✅ |
| `text-ink/68` sobre `cream` dark | **7.98:1** | ✅ | ✅ |

### Ajustes obrigatórios para o CRM (AA em texto pequeno)

1. **Não usar `text-ink/35` nem `text-ink/40`** para texto informativo no tema claro. Reservar para elementos decorativos com `aria-hidden`.
2. **`text-ink/50` e `text-ink/55`** só podem ser usados em texto ≥ 18.66px bold ou ≥ 24px regular. Para corpo/hint pequeno, subir para `text-ink/68` (~5.46:1) ou usar `#5C645D`.
3. Eyebrows e labels de 10–11px com `text-ink/35` (ex.: `Brand` compacto) precisam de cor sólida mais escura no claro.
4. Manter os pares de estado já aprovados (`brand-700/brand-50`, `rose-700/rose-50`, `sky-700/sky-50`, `amber-700/amber-50`).
5. `focus-visible` com `ring-brand-500` sobre `cream` tem 3.5:1 — atende ao requisito de 3:1 para indicador de foco.

---

## 9. PWA e metadados

| Item | Referência | Observação para o CRM |
|---|---|---|
| `manifest` | **Não possui** | O CRM deve manter o seu. Ajustar `theme_color`/`background_color` para `#F5F2EA` (claro) e `#08100C` (escuro), com ícones coerentes. |
| Ícone | `public/favicon.svg` | O CRM tem ícones próprios; recriar com a nova paleta. |
| `theme-color` | 2 metas com `prefers-color-scheme` | Replicar no `index.html`. |
| `color-scheme` | `light dark` | Replicar. |
| Fonte | Google Fonts via CDN | Para PWA/offline, avaliar self-host ou `font-display: swap` já presente. |
| Safe areas | `env(safe-area-inset-bottom)` | Replicar na navegação inferior. |

---

## 10. Como aplicar no CRM (regras para os próximos passos)

1. Criar tokens equivalentes em `frontend/tailwind.config` e variáveis CSS globais:
   - `--crm-cream`, `--crm-paper`, `--crm-ink` (triplas RGB) + escala `brand` e `lime`.
2. **Proibido** hex solto em componentes (`bg-[#534AB7]`, `text-[#BA7517]` etc. devem desaparecer).
3. Mapear o design atual para o novo:
   - `#1A1A1A` (fundo escuro atual) → `cream` / `paper` (tema claro padrão).
   - `#26215C` / `#534AB7` (roxo) → `brand-950` / `brand-500`.
   - `#FAC775` / `#BA7517` (âmbar) → `lime` / `amber-700`.
   - Botões `rounded-full` permanecem; cards migram para `rounded-3xl` + `.card`.
4. Preservar `lib/api.ts`, autenticação, PWA, push, PDF, WhatsApp e o chat de IA — mudança apenas visual.
5. Reimplementar `fade-up` com `prefers-reduced-motion`.
6. Adicionar a navegação inferior mobile apenas se o CRM ainda não tiver padrão equivalente; não remover navegação existente.
7. Tema escuro é opcional para o CRM: a referência suporta, mas o requisito é **não quebrar** o que existe. Se implementado, usar a mesma chave de preferência e o script anti-flash.

---

## 11. Decisões de aplicação no CRM (confirmadas)

| Decisão | Escolha | Justificativa |
|---|---|---|
| Tema | **Claro por padrão**, com alternância `claro` / `escuro` / `sistema` | Fiel à referência; mantém a possibilidade de escuro sem perder o novo visual |
| Storage do tema | `crm:theme` | Evita colisão com a chave `fin:theme` da referência |
| Fonte | **Self-hosted** (`@fontsource-variable/plus-jakarta-sans`) | PWA/offline sem depender do CDN do Google Fonts |
| Ícones da navegação | **SVG de linha** reimplementados | Substituem os emojis e acompanham a linguagem visual da referência |
| Cores dos gráficos | `var(--color-*)` lidos do tema | Recharts acompanha claro/escuro sem duplicar hex em JS |
| Tailwind | Tokens em `@theme` (v4) no `index.css` | O projeto não usa `tailwind.config.js` |

## 12. Resumo executivo dos tokens

```
Fundos:      cream #F5F2EA  |  paper #FCFBF7
Texto:       ink #14211A
Marca:       brand-500 #348F57  |  brand-700 #1E5B39  |  brand-950 #0B2117
Destaque:    lime #D8F36B (hover #C9EB52)
Estados:     ok brand-50/700 · atenção amber-50/700 · erro rose-50/700 · info sky-50/700
Bordas:      ink/6% (card) · ink/10% (campo) · branco/8% (card dark)
Fonte:       Plus Jakarta Sans 400–800
Raios:       full (botões/chips) · xl 12 · 2xl 16 · 3xl 24 · 4xl 32
Sombras:     card e float (ver seção 3.2)
Motion:      fade-up 0.35s ease-out · transições 150ms · active:scale 0.98
Dark:        classe .dark · cream #08100C · paper #101C15 · ink #E8F1EA
Breakpoints: sm 640 · lg 1024 (sidebar fixa, bottom nav oculta)
```
