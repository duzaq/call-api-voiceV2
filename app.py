import asyncio
import os
import logging
import uuid

import aiohttp
from flask import Flask, request, jsonify
from deepgram import Deepgram
from gtts import gTTS
from dotenv import load_dotenv
import openai

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Carregar chaves de API
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', 150))

# Função auxiliar para transcrição de áudio com Deepgram
async def _transcribe_audio_deepgram(audio_url):
    try:
        deepgram = Deepgram(DEEPGRAM_API_KEY)
        source = {'url': audio_url}
        response = await deepgram.transcription.prerecorded(source, {'punctuate': True})
        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
        logging.info(f"Transcrição Deepgram: {transcript}")
        return transcript
    except Exception as e:
        logging.error(f"Erro na transcrição Deepgram: {e}")
        raise

# Função auxiliar para geração de resposta com OpenAI (agora assíncrona)
async def _generate_response_openai(prompt):
    try:
        async with aiohttp.ClientSession() as session:
            openai.aiosession.set(session)
            response = await openai.ChatCompletion.acreate(
                api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um assistente útil."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=OPENAI_MAX_TOKENS
            )
            answer = response['choices'][0]['message']['content'].strip()
            logging.info(f"Resposta OpenAI: {answer}")
            return answer
    except Exception as e:
        logging.error(f"Erro na geração de resposta OpenAI: {e}")
        raise

# Função auxiliar para conversão de texto para áudio com gTTS (agora assíncrona)
async def _text_to_speech_gtts(text, output_file='output.mp3'):
    def _save_audio():
        try:
            tts = gTTS(text=text, lang='pt')
            # Usar um caminho relativo para salvar no diretório montado 'audio'
            save_path = os.path.join("audio", output_file)
            tts.save(save_path)
            logging.info(f"Áudio salvo em: {save_path}")
            return output_file  # Retornar apenas o nome do arquivo
        except Exception as e:
            logging.error(f"Erro na conversão de texto para áudio com gTTS: {e}")
            raise

    # Executar a operação de I/O em um thread separado para não bloquear o loop de eventos
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _save_audio)

# Função para roteamento de chamada (agora assíncrona e com tratamento de erros)
async def route_call(caller, callee):
    """
    Roteia a chamada com base no chamador e no destinatário.

    Args:
        caller: O número ou ID do chamador.
        callee: O número ou ID do destinatário.

    Returns:
        Uma string indicando o resultado do roteamento ou um código de erro.
    Raises:
        RouteCallException: Se houver um erro no roteamento da chamada.
    """
    try:
        if callee == "suporte":
            return "SUPP" # Exemplo de código de retorno
        elif callee == "vendas":
            return "VEND" # Exemplo de código de retorno
        else:
            raise RouteCallException(f"Destinatário desconhecido: {callee}")
    except Exception as e:
        logging.error(f"Erro ao rotear chamada de {caller} para {callee}: {e}")
        raise RouteCallException(f"Erro interno ao rotear chamada: {e}")

class RouteCallException(Exception):
    """Exceção para erros de roteamento de chamada."""
    pass

# Endpoint principal para lidar com chamadas SIP
@app.route('/sip/call', methods=['POST'])
async def handle_call():
    data = request.json

    # Validação básica de entrada
    caller = data.get('caller')
    callee = data.get('callee')
    audio_url = data.get('audio_url')
    call_id = data.get('call_id', str(uuid.uuid4())) # Adiciona um ID de chamada

    if not all([caller, callee, audio_url]):
        return jsonify({"error": "Campos 'caller', 'callee' e 'audio_url' são obrigatórios."}), 400
    if not audio_url.startswith(('http://', 'https://')):
        return jsonify({"error": "O 'audio_url' deve ser um URL válido."}), 400

    logging.info(f"Chamada recebida de {caller} para {callee}, áudio: {audio_url}, Call-ID: {call_id}")

    try:
        # Transcrever áudio
        transcription = await _transcribe_audio_deepgram(audio_url)

        # Roteamento de Chamada
        try:
            routing_response = await route_call(caller, callee)
        except RouteCallException as e:
            return jsonify({"error": str(e)}), 400

        # Gerar resposta
        response_text = await _generate_response_openai(transcription)

        # Converter resposta em áudio
        # Gera um nome de arquivo único para o áudio de resposta
        unique_id = str(uuid.uuid4())
        response_audio_filename = f"response-{unique_id}.mp3"

        # audio_file agora é apenas o nome do arquivo
        audio_file = await _text_to_speech_gtts(response_text, response_audio_filename)

        # Modificar o retorno para incluir o URL do áudio de resposta
        return jsonify({
            "status": "processed",
            "call_id": call_id,
            "transcription": transcription,
            "response": response_text,
            "audio_file": f"http://nginx/audio/{audio_file}",
            "routing_response": routing_response
        })

    except Exception as e:
        logging.error(f"Erro no processamento da chamada {call_id}: {e}")
        return jsonify({"error": "Erro no processamento da chamada.", "detail": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_RUN_PORT', 5060)))
