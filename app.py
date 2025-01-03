from flask import Flask, request, jsonify
from deepgram import Deepgram
import asyncio
import openai
from gtts import gTTS
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# Carregar chaves de API do ambiente
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

async def transcribe_audio(audio_url):
    try:
        deepgram = Deepgram(DEEPGRAM_API_KEY)
        source = {'url': audio_url}
        print(f"Transcrevendo áudio da URL: {audio_url}")  # Log para depuração
        response = await deepgram.transcription.prerecorded(source, {'punctuate': True})
        print(f"Resposta da Deepgram: {response}")  # Log para depuração
        return response['results']['channels'][0]['alternatives'][0]['transcript']
    except Exception as e:
        print(f"Erro ao transcrever áudio: {e}")  # Log para depuração
        return ""

def generate_response(prompt):
    openai.api_key = OPENAI_API_KEY
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150
    )
    return response['choices'][0]['message']['content'].strip()

def text_to_speech(text, output_file='output.mp3'):
    tts = gTTS(text=text, lang='pt')
    tts.save(output_file)
    return output_file

def route_call(caller, callee):
    if callee == "suporte":
        return "Você será conectado ao suporte técnico."
    elif callee == "vendas":
        return "Você será conectado ao departamento de vendas."
    else:
        return "Desculpe, não reconhecemos o número discado."

@app.route('/sip/call', methods=['POST'])
async def handle_call():  # Usando async def
    data = request.json
    caller = data.get('caller')
    callee = data.get('callee')
    audio_url = data.get('audio_url')

    print(f"Iniciando transcrição do áudio: {audio_url}")  # Log para depuração

    # Transcrever áudio
    transcription = await transcribe_audio(audio_url)  # Usando await
    print(f"Transcrição: {transcription}")

    # Gerar resposta com OpenAI
    response_text = generate_response(transcription)
    print(f"Resposta gerada: {response_text}")

    # Converter resposta em áudio
    audio_file = text_to_speech(response_text)
    print(f"Áudio gerado: {audio_file}")

    # Roteamento de chamada
    routing_response = route_call(caller, callee)
    print(f"Roteamento: {routing_response}")

    # Retornar resposta
    return jsonify({
        "status": "processed",
        "transcription": transcription,
        "response": response_text,
        "audio_file": audio_file,
        "routing_response": routing_response
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_RUN_PORT', 5060)))
