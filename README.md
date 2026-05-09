# 🫁 Radiología Torácica — Actualización Científica Mensual

Sistema automatizado de actualización mensual en radiología torácica.  
Monitoriza 13 revistas indexadas, detecta los artículos más citados y genera resúmenes escritos + podcast de 30 minutos cada mes.

---

## ¿Qué hace este sistema?

El día 1 de cada mes, automáticamente:

1. **Busca en PubMed** todos los artículos del mes anterior en 13 revistas seleccionadas
2. **Busca en Semantic Scholar** los 10 artículos más citados fuera de esas revistas, por tema
3. **Clasifica** los artículos en 11 temas clínicos con Claude AI
4. **Genera resúmenes** de actualización (state of the art) para cada tema
5. **Genera el guion** de un podcast de 30 minutos con dos locutores (Ana y Carlos)
6. **Convierte el guion a audio** MP3 con ElevenLabs o OpenAI TTS
7. **Publica todo** en una web accesible desde el navegador (GitHub Pages)

---

## Temas cubiertos

| # | Tema |
|---|------|
| 1 | Infecciones y procesos inflamatorios torácicos |
| 2 | EPID (Enfermedad Pulmonar Intersticial Difusa) |
| 3 | Neoplasia Pulmonar |
| 4 | Nódulo Pulmonar |
| 5 | EPOC y Patología de la Vía Aérea |
| 6 | TEP e Hipertensión Pulmonar |
| 7 | Cardiopatía Isquémica |
| 8 | Miocardiopatías |
| 9 | RM Torácica (no cardiaca) |
| 10 | Avances en Imagen Cardiaca |
| 11 | IA en Radiología Torácica |

---

## Revistas monitorizadas (13)

Radiology · RadioGraphics · European Radiology · AJR · Journal of Thoracic Imaging · European Journal of Radiology · JTCVS Imaging · JACC Cardiovascular Imaging · Circulation Cardiovascular Imaging · European Respiratory Journal · Chest · Insights into Imaging · Radiología (SERAM/Elsevier)

---

## Instalación paso a paso

### Paso 1: Crear cuenta en GitHub
Si no tienes cuenta: https://github.com/signup (gratuito)

### Paso 2: Crear el repositorio
1. Ve a https://github.com/new
2. Nombre del repositorio: `radiologia-toracica-update`
3. Visibilidad: **Private** (recomendado) o Public
4. No inicialices con README
5. Clic en **Create repository**

### Paso 3: Subir el código
En tu ordenador, abre una terminal y ejecuta:

```bash
# Clona el repositorio vacío
git clone https://github.com/TU_USUARIO/radiologia-toracica-update.git
cd radiologia-toracica-update

# Copia todos los archivos de este proyecto aquí
# (arrastra y suelta o copia la carpeta)

# Sube todo
git add .
git commit -m "Initial setup"
git push origin main
```

### Paso 4: Obtener las claves de API

#### Claude (Anthropic) — OBLIGATORIO
1. Ve a https://console.anthropic.com
2. API Keys → Create Key
3. Copia la clave (empieza por `sk-ant-...`)
4. Coste estimado: ~$3-5/mes

#### ElevenLabs — Para el podcast (recomendado)
1. Ve a https://elevenlabs.io y crea cuenta gratuita
2. Profile → API Key
3. Copia la clave
4. Plan gratuito: 10.000 caracteres/mes (suficiente para pruebas)
5. Plan Starter ($5/mes): 30.000 caracteres — suficiente para podcast mensual

#### NCBI/PubMed — Opcional pero recomendado
1. Ve a https://www.ncbi.nlm.nih.gov/account/
2. Crea cuenta gratuita → Account Settings → API Key Management
3. Sin clave: límite de 3 requests/seg. Con clave: 10 requests/seg

### Paso 5: Configurar las claves en GitHub (Secrets)
1. Ve a tu repositorio en GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. Clic en **New repository secret** y añade:

| Nombre | Valor |
|--------|-------|
| `ANTHROPIC_API_KEY` | tu clave de Claude |
| `ELEVENLABS_API_KEY` | tu clave de ElevenLabs (opcional) |
| `NCBI_API_KEY` | tu clave de PubMed (opcional) |

### Paso 6: Activar GitHub Pages
1. Ve a **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **gh-pages** / root
4. Clic en **Save**

La URL de tu web será: `https://TU_USUARIO.github.io/radiologia-toracica-update`

### Paso 7: Primera ejecución manual
1. Ve a **Actions** → **Monthly Radiology Update**
2. Clic en **Run workflow** → **Run workflow**
3. Espera ~30-60 minutos
4. Accede a tu URL de GitHub Pages

---

## Añadir temas ad-hoc para el próximo mes

Edita el archivo `config/adhoc_topics.yaml`:

```yaml
adhoc_topics:
  - name: "Photon counting CT en tórax"
    query: "photon counting CT thorax lung clinical"
    date_range: "3months"
    max_results: 15
```

Sube el cambio antes del día 1 del mes:
```bash
git add config/adhoc_topics.yaml
git commit -m "Add adhoc topic for next month"
git push
```

---

## Ejecución manual con opciones

Desde la pestaña **Actions** → **Run workflow**, puedes elegir:

- ☐ `no_audio` — No genera el podcast (más rápido)
- ☐ `topics_only` — Solo resúmenes, sin podcast
- ☐ `dry_run` — Solo busca artículos (para testear)

---

## Estructura del proyecto

```
├── .github/workflows/
│   └── monthly_update.yml    # Automatización GitHub Actions
├── config/
│   ├── topics.yaml            # 11 temas con términos MeSH
│   ├── journals.yaml          # 13 revistas con ISSNs
│   └── adhoc_topics.yaml      # ← EDITAR para temas ad-hoc
├── scripts/
│   ├── main.py                # Orquestador principal
│   ├── fetcher.py             # PubMed + Semantic Scholar
│   ├── generator.py           # Claude AI (resúmenes + guion)
│   ├── audio.py               # ElevenLabs / OpenAI TTS
│   └── dashboard.py           # Constructor del dashboard web
├── docs/                      # Output web (publicado en GitHub Pages)
└── requirements.txt
```

---

## Costes estimados mensuales

| Servicio | Uso estimado | Coste |
|----------|-------------|-------|
| Claude API | ~200K tokens/mes | ~$3-5 |
| ElevenLabs | ~5000 chars/mes | $0 (free tier) |
| GitHub Actions | <60 min/mes | $0 |
| PubMed / Semantic Scholar | ilimitado | $0 |
| **Total** | | **~$3-5/mes** |

---

## Soporte

Cualquier problema: revisa el log en `pipeline.log` o los logs de GitHub Actions.
