import streamlit as st
import requests
import json
import uuid
import base64

# --- Configurações da API ---
# As chaves de API devem ser armazenadas de forma segura.
# Em um ambiente Streamlit Cloud, use st.secrets.
# Para execução local, você pode definir as variáveis de ambiente ou
# colocar as chaves diretamente aqui (APENAS PARA TESTE LOCAL E NUNCA EM PRODUÇÃO).
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
IMAGEN_API_KEY = st.secrets.get("IMAGEN_API_KEY", "") # Pode ser a mesma chave ou outra, dependendo da sua configuração

GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
IMAGEN_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={IMAGEN_API_KEY}"

# --- Funções de Geração de API ---

def generate_text(prompt, schema=None):
    """
    Função para gerar texto usando a API Gemini.
    """
    chat_history = []
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {"contents": chat_history}
    if schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": schema
        }

    st.session_state.error_message = None # Limpa qualquer erro anterior
    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )
        response.raise_for_status() # Lança exceção para status de erro HTTP

        result = response.json()
        if result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:
            text = result["candidates"][0]["content"].get("parts")[0].get("text")
            # Verifica se o texto é uma string JSON válida antes de tentar parsear
            if schema:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    st.session_state.error_message = f"Erro ao decodificar JSON esperado da API Gemini. Resposta recebida: {text}"
                    return None
            return text
        else:
            st.session_state.error_message = "Resposta inesperada da API Gemini para texto."
            return None
    except requests.exceptions.RequestException as e:
        st.session_state.error_message = f"Erro ao comunicar com a API Gemini: {e}. Verifique sua chave de API e conexão."
        return None
    except Exception as e:
        st.session_state.error_message = f"Ocorreu um erro desconhecido ao gerar texto: {e}"
        return None

def generate_image(image_prompt, style):
    """
    Função para gerar uma imagem usando a API Imagen.
    """
    full_image_prompt = f"{image_prompt}, estilo: {style}"
    payload = {
        "instances": {"prompt": full_image_prompt},
        "parameters": {"sampleCount": 1}
    }

    st.session_state.error_message = None # Limpa qualquer erro anterior
    try:
        response = requests.post(
            IMAGEN_API_URL,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )
        response.raise_for_status() # Lança exceção para status de erro HTTP

        result = response.json()
        if result.get("predictions") and len(result["predictions"]) > 0 and result["predictions"][0].get("bytesBase64Encoded"):
            return f"data:image/png;base64,{result['predictions'][0]['bytesBase64Encoded']}"
        else:
            st.session_state.error_message = "Resposta inesperada da API Imagen para imagem."
            return None
    except requests.exceptions.RequestException as e:
        st.session_state.error_message = f"Erro ao comunicar com a API Imagen: {e}. Verifique sua chave de API e conexão."
        return None
    except Exception as e:
        st.session_state.error_message = f"Ocorreu um erro desconhecido ao gerar imagem: {e}"
        return None

# --- Variáveis de Estado do Streamlit ---
def initialize_session_state():
    """Inicializa as variáveis de estado da sessão."""
    if "story_scenes" not in st.session_state:
        st.session_state.story_scenes = [] # [{image: url, caption: text, prompt: text}]
    if "story_context" not in st.session_state:
        st.session_state.story_context = [] # Para o contexto do LLM
    if "character_description" not in st.session_state:
        st.session_state.character_description = ""
    if "options" not in st.session_state:
        st.session_state.options = [] # Opções para a próxima cena
    if "selected_style" not in st.session_state:
        st.session_state.selected_style = 'realista'
    if "loading" not in st.session_state:
        st.session_state.loading = False
    if "error_message" not in st.session_state:
        st.session_state.error_message = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4()) # Gera um ID de usuário único por sessão

initialize_session_state()

# --- Opções de Estilos de Imagem ---
IMAGE_STYLES = [
    {'label': 'Realista', 'value': 'realista'},
    {'label': 'Desenho Animado', 'value': 'desenho animado'},
    {'label': 'Pintura a Óleo', 'value': 'pintura a óleo'},
    {'label': 'Ficção Científica', 'value': 'ficção científica'},
    {'label': 'Fantasia', 'value': 'fantasia'},
    {'label': 'Aquarela', 'value': 'aquarela'},
    {'label': 'Pixel Art', 'value': 'pixel art'},
]

# --- Lógica Principal da História ---

def start_story(initial_prompt):
    """
    Inicia uma nova história com base no prompt inicial.
    """
    if not initial_prompt.strip():
        st.session_state.error_message = "Por favor, digite um prompt para iniciar a história."
        return

    st.session_state.loading = True
    st.session_state.error_message = None
    st.session_state.story_scenes = []
    st.session_state.story_context = []
    st.session_state.character_description = ""
    st.session_state.options = []
    
    with st.spinner("Gerando a primeira cena e personagem..."):
        try:
            # 1. Gerar descrição do personagem e legenda da cena inicial
            initial_character_and_scene_prompt = f"""
            Com base no seguinte prompt de história, descreva os personagens principais e o cenário inicial em detalhe.
            Foque em detalhes que seriam úteis para uma geração de imagem.
            Prompt do usuário: "{initial_prompt}"

            Responda no formato JSON. Exemplo:
            {{ "characterDescription": "...", "initialSceneCaption": "..." }}
            """
            initial_details_schema = {
                "type": "OBJECT",
                "properties": {
                    "characterDescription": {"type": "STRING"},
                    "initialSceneCaption": {"type": "STRING"}
                }
            }
            initial_details = generate_text(initial_character_and_scene_prompt, initial_details_schema)

            if not initial_details or not initial_details.get("characterDescription") or not initial_details.get("initialSceneCaption"):
                raise Exception("Não foi possível gerar os detalhes iniciais da história.")

            st.session_state.character_description = initial_details["characterDescription"]
            scene_caption = initial_details["initialSceneCaption"]
            image_prompt = f"{st.session_state.character_description}. {scene_caption}"

            # 2. Gerar imagem da primeira cena
            image_url = generate_image(image_prompt, st.session_state.selected_style)
            if not image_url:
                raise Exception("Não foi possível gerar a imagem da primeira cena.")

            new_scene = {"image": image_url, "caption": scene_caption, "prompt": initial_prompt}
            st.session_state.story_scenes.append(new_scene)
            st.session_state.story_context.append(new_scene)

            # 3. Gerar opções para a próxima cena
            options_prompt = f"""
            A história atual é: "{scene_caption}".
            Gere 3 opções distintas e concisas para a próxima cena.
            Responda no formato JSON. Exemplo:
            {{ "options": ["Opção 1", "Opção 2", "Opção 3"] }}
            """
            options_schema = {
                "type": "OBJECT",
                "properties": {
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}}
                }
            }
            generated_options = generate_text(options_prompt, options_schema)
            st.session_state.options = generated_options.get("options", []) if generated_options else []

        except Exception as e:
            st.session_state.error_message = f"Ocorreu um erro ao iniciar a história: {e}"
        finally:
            st.session_state.loading = False
            # O Streamlit irá rerunnar automaticamente após a execução do callback e a alteração de st.session_state

def generate_next_scene(selected_option=None):
    """
    Gera a próxima cena da história com base em uma opção selecionada ou prompt personalizado.
    """
    next_scene_prompt_value = selected_option if selected_option else st.session_state.custom_prompt_input.strip()

    if not next_scene_prompt_value:
        st.session_state.error_message = "Selecione uma opção ou digite um prompt para a próxima cena."
        return

    st.session_state.loading = True
    st.session_state.error_message = None
    
    with st.spinner("Gerando a próxima cena e imagem..."):
        try:
            last_scene = st.session_state.story_scenes[-1]

            # 1. Gerar a legenda da próxima cena
            caption_generation_prompt = f"""
            A história terminou com a seguinte cena: "{last_scene['caption']}".
            O próximo evento escolhido é: "{next_scene_prompt_value}".
            Escreva a próxima parte da história em um parágrafo conciso, continuando de forma lógica.
            """
            scene_caption = generate_text(caption_generation_prompt)
            if not scene_caption:
                raise Exception("Não foi possível gerar a legenda da próxima cena.")

            # 2. Gerar a imagem para a próxima cena
            image_prompt = f"{st.session_state.character_description}. {scene_caption}"
            image_url = generate_image(image_prompt, st.session_state.selected_style)
            if not image_url:
                raise Exception("Não foi possível gerar a imagem da próxima cena.")

            new_scene = {"image": image_url, "caption": scene_caption, "prompt": next_scene_prompt_value}
            st.session_state.story_scenes.append(new_scene)
            st.session_state.story_context.append(new_scene) # Adiciona ao contexto

            # 3. Gerar novas opções para a continuação
            options_prompt = f"""
            A história agora é: "{scene_caption}".
            Gere 3 opções distintas e concisas para continuar a história.
            Responda no formato JSON. Exemplo:
            {{ "options": ["Opção A", "Opção B", "Opção C"] }}
            """
            options_schema = {
                "type": "OBJECT",
                "properties": {
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}}
                }
            }
            generated_options = generate_text(options_prompt, options_schema)
            st.session_state.options = generated_options.get("options", []) if generated_options else []

        except Exception as e:
            st.session_state.error_message = f"Ocorreu um erro ao gerar a próxima cena: {e}"
        finally:
            st.session_state.loading = False
            # O Streamlit irá rerunnar automaticamente após a execução do callback e a alteração de st.session_state

def clear_story():
    """
    Limpa a história atual e reinicia o aplicativo.
    """
    st.session_state.story_scenes = []
    st.session_state.story_context = []
    st.session_state.character_description = ""
    st.session_state.options = []
    st.session_state.loading = False
    st.session_state.error_message = None
    # Força um rerun para garantir que toda a UI seja redefinida para o estado inicial
    st.rerun()

# --- Layout da Interface do Usuário no Streamlit ---

st.set_page_config(layout="centered", page_title="Gerador de Histórias Ilustradas", page_icon="✨")

# Título principal
st.markdown(
    """
    <h1 style='text-align: center; color: #8B5CF6; font-size: 3em; font-weight: bold; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);'>
        Gerador de Histórias Ilustradas
    </h1>
    """,
    unsafe_allow_html=True
)

# Área para exibir mensagens de erro
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# Botão para limpar a história (sempre visível se houver história)
if st.session_state.story_scenes:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.button("Limpar História Salva e Começar de Novo", on_click=clear_story, type="secondary", use_container_width=True)
    st.markdown("---") # Separador visual

# Seção inicial para o prompt do usuário e seleção de estilo
if not st.session_state.story_scenes and not st.session_state.loading:
    st.markdown("### Comece sua aventura! Digite um prompt para a primeira cena da sua história.")
    initial_prompt = st.text_area(
        "Prompt Inicial:",
        placeholder="Ex: 'Um jovem explorador encontra um mapa antigo numa floresta mágica.'",
        height=100,
        key="initial_prompt_input"
    )

    style_options = {style['label']: style['value'] for style in IMAGE_STYLES}
    selected_style_label = st.selectbox(
        "Estilo da Imagem:",
        options=list(style_options.keys()),
        index=list(style_options.values()).index(st.session_state.selected_style),
        key="image_style_select"
    )
    st.session_state.selected_style = style_options[selected_style_label]

    st.button(
        "Iniciar História",
        on_click=lambda: start_story(initial_prompt),
        disabled=st.session_state.loading or not initial_prompt.strip(),
        type="primary",
        use_container_width=True
    )

# Contêiner onde as cenas da história serão exibidas
if st.session_state.story_scenes:
    for i, scene in enumerate(st.session_state.story_scenes):
        st.markdown(f"## Cena {i + 1}")
        st.image(scene['image'], caption=f"Cena {i + 1}", use_column_width="always")
        st.markdown(f"<p style='font-size: 1.1em; text-align: justify;'>{scene['caption']}</p>", unsafe_allow_html=True)
        st.markdown("---") # Separador entre cenas


    # Seção para opções de continuação da história ou prompt personalizado
    if not st.session_state.loading:
        st.markdown("### O que acontece em seguida?")

        # Botões de opção
        if st.session_state.options:
            cols = st.columns(len(st.session_state.options))
            for i, option_text in enumerate(st.session_state.options):
                with cols[i]:
                    st.button(
                        option_text,
                        on_click=lambda opt=option_text: generate_next_scene(opt),
                        disabled=st.session_state.loading,
                        use_container_width=True,
                        help="Clique para continuar com esta opção"
                    )
        else:
            st.info("Nenhuma opção generada para esta cena. Tente um prompt personalizado.")

        st.markdown("#### Ou crie sua própria cena:")
        custom_prompt = st.text_area(
            "Prompt Personalizado:",
            placeholder="Ex: 'O explorador segue o mapa até uma cachoeira escondida.'",
            height=80,
            key="custom_prompt_input"
        )
        st.button(
            "Gerar Próxima Cena",
            on_click=lambda: generate_next_scene(None),
            disabled=st.session_state.loading or not custom_prompt.strip(),
            type="primary",
            use_container_width=True
        )

# Exibição do ID do usuário para depuração
st.markdown(f"<p style='font-size: 0.8em; color: #9CA3AF; text-align: center; margin-top: 50px;'>ID da Sessão: {st.session_state.user_id}</p>", unsafe_allow_html=True)
