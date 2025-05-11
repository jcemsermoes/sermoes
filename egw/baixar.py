import os
import sys
import time
import json
import hashlib
import requests
from urllib.parse import urlsplit
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor
import threading  # Para obter o nome da thread
import traceback  # Importando o módulo traceback para capturar exceções e tracebacks

# Códigos ANSI para colorir o terminal
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

#livros_baixados = 0
falhas = {}

# Atribuição dos IDs das threads
thread_ids = {}

# Função para remover artigos no final do título e corrigir vírgulas
def remove_article_from_title(title):
    artigos = ["A", "O", "As", "Os", "Uma", "Um", "Umas", "Uns"]
    title_parts = title.strip().split()
    
    # Remover o artigo no final, se existir
    if title_parts and title_parts[-1] in artigos:
        title_parts.pop()
    
    # Remover a vírgula no final do título, se houver
    if title_parts and title_parts[-1].endswith(','):
        title_parts[-1] = title_parts[-1][:-1]
    
    return " ".join(title_parts)

def ensure_dir_exists(path):
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    os.makedirs(path, exist_ok=True)
    return path

# Função para calcular o hash SHA-256 de um arquivo
def get_sha256_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Ler o arquivo em pedaços e atualizar o hash
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def download_file(url, dest_path, filename=None, thread_id=None, progress=''):    
    try:
        response = requests.get(url, stream=True, timeout=10)
        if not filename:
            filename = os.path.basename(urlsplit(url).path)

        filename = limpar_nome_arquivo(filename)
        full_path = os.path.join(dest_path, filename)
        total = int(response.headers.get('content-length', 0))

        if os.path.exists(full_path) and os.path.getsize(full_path) > 0:            
            print(f"{GREEN}[{thread_id}] [{progress}] [✓] Já no destino.: '{filename}'.{RESET}")
            return full_path

        with open(full_path, 'wb') as file, tqdm(
            desc=filename,
            total=total,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

        if os.path.exists(full_path) and os.path.getsize(full_path) > 0:                                             
            print(f"{GREEN}[{thread_id}] [{progress}] [✓] baixado.......: '{filename or url}'.{RESET}")
            return full_path
        else:
            print(f"{YELLOW}[{thread_id}] [{progress}] [W] Falha/Vazio...: '{filename or url}'{RESET}")

    except Exception as e:                                          
        print(f"{RED}[{thread_id}] [{progress}] [ERRO] Falha baixa...: '{filename or url}': {e}{RESET}")
        return None
    
    return False


def create_source_json(title, download_dir, refs, thread_id, progress=''):
    if refs:  # Só cria o arquivo se houver pelo menos uma URL        
        source_file = os.path.join(download_dir, f"{limpar_nome_arquivo(title)}.source.json")
        with open(source_file, 'w') as json_file:
            json.dump(refs, json_file, indent=4)                                         
        print(f"{GREEN}[{thread_id}] [{progress}] [✓] Criado........: '{limpar_nome_arquivo(title)}.source.json'.{RESET}")

def registrar_falha(titulo, erro, url, exception=None, traceback_info=None, thread_id=None):
    global falhas
    
    error_message = erro
    if exception:
        error_message = str(exception)
    
    falhas[titulo] = {
        "erro": error_message,
        "url_principal": url,
        "exception": str(exception) if exception else None,
        "traceback": traceback_info,
    }

    # Apenas o processo pai escreve no arquivo JSON
    if os.getpid() == os.getppid():
        with open('falhas.json', 'w') as f:
            json.dump(falhas, f, indent=4)

def limpar_nome_arquivo(nome):
    # Lista de caracteres proibidos no sistema de arquivos (Windows)
    caracteres_invalidos = [':']
    for char in caracteres_invalidos:
        nome = nome.replace(char, ' -')  # Substitui os caracteres inválidos por "_"    
    
    # Lista de caracteres proibidos no sistema de arquivos (Windows)
    caracteres_invalidos = ['<', '>', '"', '/', '\\', '|', '?', '*']
    for char in caracteres_invalidos:
        nome = nome.replace(char, '')  # Substitui os caracteres inválidos por "_"

    return nome

def padd_progress(feito=0, total=0):
    return f"{f"{feito}".zfill(3)}/{f"{total}".zfill(3)}"

def main(url, download_dir, thread_id):
    livros_baixados = 0
    arquivos_baixados = 0

    download_dir = ensure_dir_exists(download_dir)

    options = FirefoxOptions()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1920, 1080)

    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)

    driver.get(url)

    # Acitar Cookies - Aguardar o botão que começa com a classe "Ripple_root__lmfsr Ripple_dark__"
    try:
        ripple_button = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "div[class^='Ripple_root__lmfsr Ripple_dark__']"
        )))

        # Mover o mouse até o botão e clicar
        actions.move_to_element(ripple_button).click().perform()
        print(f"{GREEN}[{thread_id}] [I] Clicado.......: Botão Ripple.{RESET}")
        time.sleep(1)  # Esperar um pouco para a ação surtir efeito

    except Exception as e:
        print(f"{YELLOW}[{thread_id}] [w] Não encontrado: Botão Ripple não encontrado ou falha ao clicar: {e}{RESET}")

    # Scroll para carregar todos os livros dinamicamente
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0

    print(f"{CYAN}[{thread_id}] [I] Iniciando a busca pelos livros...{RESET}")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            scroll_attempts += 1
            if scroll_attempts >= 3:
                print(f"{CYAN}[{thread_id}] [I] Scroll completo. Carregando livros finalizados.{RESET}")
                break
        else:
            scroll_attempts = 0
            last_height = new_height

    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ReactVirtualized__Grid__innerScrollContainer")))

    books = driver.find_elements(By.CLASS_NAME, "book-list-item")

    print(f"{GREEN}[{thread_id}] [{padd_progress(arquivos_baixados,len(books)*2)}] [✓] Encontrados {len(books)} livros para download.{RESET}")

    for book in books:
        try:            
            # Movendo o mouse sobre o livro para ativar o hover
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", book)
            time.sleep(0.5)
            actions.move_to_element(book).perform()
            time.sleep(1.5)

            # Tentando obter o título
            title_elem = book.find_elements(By.CLASS_NAME, "title")
            title = title_elem[0].text.strip().replace("/", "_") if title_elem else "Desconhecido"

            # Remover artigo do título, se houver, e corrigir vírgulas
            title = remove_article_from_title(title)

            download_panels = book.find_elements(By.CLASS_NAME, "book-download-links")
            if not download_panels:
                print(f"{YELLOW}[{thread_id}] [{padd_progress(arquivos_baixados,len(books)*2)}] [w] ({title}): Painel de download não encontrado.{RESET}")
                continue

            download_panel = download_panels[0]            

            links = download_panel.find_elements(By.TAG_NAME, "a")
            has_download = False

            refs = {}

            for link in links:
                href = link.get_attribute("href")
                if href.endswith(".pdf"):                                                    
                    print(f"{BLUE}[{thread_id}] [{padd_progress(arquivos_baixados,len(books)*2)}] [I] Baixando......: '{title}' (PDF)...{RESET}")
                    downloaded_file = download_file(href, download_dir, f"{title}.pdf", thread_id, padd_progress(arquivos_baixados,len(books)*2))

                    if downloaded_file and os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 0:
                        timestamp = int(time.time())
                        sha256_hash = get_sha256_hash(downloaded_file)
                        refs[href] = {"acesso": timestamp, "sha256": sha256_hash}
                        has_download = True

                        arquivos_baixados += 1

                elif href.endswith(".epub"):
                    print(f"{BLUE}[{thread_id}] [{padd_progress(arquivos_baixados,len(books)*2)}] [I] Baixando......: '{title}' (EPUB)...{RESET}")
                    downloaded_file = download_file(href, download_dir, f"{title}.epub", thread_id, padd_progress(arquivos_baixados,len(books)*2))
                    if downloaded_file and os.path.exists(os.path.join(download_dir, f"{title}.pdf")) and os.path.getsize(os.path.join(download_dir, f"{title}.pdf")) > 0:
                        timestamp = int(time.time())
                        sha256_hash = get_sha256_hash(downloaded_file)
                        refs[href] = {"acesso": timestamp, "sha256": sha256_hash}
                        has_download = True
                        
                        arquivos_baixados += 1

            if has_download:
                livros_baixados += 1
                # Criar o arquivo .source.json com as URLs dos arquivos baixados
                create_source_json(title, download_dir, refs, thread_id, padd_progress(arquivos_baixados,len(books)*2))

            # Injetando JavaScript para esconder o painel de sobreposição exibido atualmente e evitar erros
            driver.execute_script(""" 
                const hoverPanel = document.querySelector('.book-description-cover');
                if (hoverPanel) {
                    hoverPanel.style.display = 'none';
                }
            """)
            time.sleep(1)  # Pausa para garantir que o painel foi ocultado

        except Exception as e:                                              
            print(f"{RED}[{thread_id}] [{padd_progress(arquivos_baixados,len(books)*2)}] [ERRO] Falha.........: '{title}': {e}{RESET}")
            
            # Capturando o traceback completo
            tb = traceback.format_exc()
            registrar_falha(title, str(e), url, e, tb, thread_id)

    driver.quit()
    return {
        "thread_id": thread_id,
        "url": url,
        "livros_baixados": livros_baixados,
        "total_livros": len(books),
        "arquivos_baixados": arquivos_baixados    
    }

# URLs das coleções para processar em paralelo
urls = [
    ("https://egwwritings.org/allCollection/pt/245", 'pt-br/livros'),
    ("https://egwwritings.org/allCollection/pt/246", 'pt-br/devocionais'),
    ("https://egwwritings.org/allCollection/en/4", 'en-us/books'),
    ("https://egwwritings.org/allCollection/en/1227", 'en-us/devotionals'),
    ("https://egwwritings.org/allCollection/en/9", 'en-us/manuscript'),
    ("https://egwwritings.org/allCollection/en/8", 'en-us/pamphlets'),
    ("https://egwwritings.org/allCollection/en/5", 'en-us/periodicals'),
    ("https://egwwritings.org/allCollection/en/10", 'en-us/misc')
]

# Iniciar o ThreadPoolExecutor para processar as URLs em paralelo
with ThreadPoolExecutor(max_workers=len(urls)) as executor:
    futures = [executor.submit(main, url, download_dir, i+1) for i, (url, download_dir) in enumerate(urls)]
    
    # Coletar resultados
    resultados = [future.result() for future in futures]

    # Exibir o resumo final após todos os threads
    print(f"\n{BOLD}{CYAN}=== RESUMO FINAL ==={RESET}")
    total_livros = total_arquivos = 0

    for r in resultados:
        print(f"{GREEN}[{r['thread_id']}] | {r['url']} | Livros: {r['livros_baixados']}/{r['total_livros']} | Arquivos baixados: {r['arquivos_baixados']}{RESET}")
        total_livros += r['livros_baixados']
        total_arquivos += r['arquivos_baixados']

    print(f"\n{BOLD}{CYAN}Total Geral:{RESET} Livros com download: {total_livros} | Arquivos baixados: {total_arquivos}")
