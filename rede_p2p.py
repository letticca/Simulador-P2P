import json
import random
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox, RadioButtons, Button

class Node:
    def __init__(self, node_id, resources):
        self.node_id = node_id
        self.resources = resources
        self.neighbors = []
        self.cache = {}
    
class P2PNetwork:
    def __init__(self):
        self.nodes = {}
        self.graph = nx.Graph() 
        self.min_neighbors = 0
        self.max_neighbors = 0

    def load_from_json(self, filepath):
        """Mecânica de ingestão: Transforma o texto JSON em objetos e nos do grafo."""
        with open(filepath, 'r') as file:
            data = json.load(file)
        
        self.min_neighbors = data['min_neighbors']
        self.max_neighbors = data['max_neighbors']

        # Passo 1: Instanciar os nós em memória e no motor gráfico
        for node_id, res_list in data['resources'].items():
            self.nodes[node_id] = Node(node_id, res_list)
            self.graph.add_node(node_id)

        # Passo 2: Construir as arestas bidirecionais
        for edge in data['edges']:
            u, v = edge[0], edge[1]
            
            # Atualiza o roteamento interno
            self.nodes[u].neighbors.append(v)
            self.nodes[v].neighbors.append(u)
            
            # Atualiza a matemática do grafo
            self.graph.add_edge(u, v)

    def validate_network(self):
        """Aplica as 4 regras de validação usando uma mistura de lógica de dicionário e Teoria dos Grafos."""
        for node_id, node in self.nodes.items():
            # Regra 1: Sem self-loops
            if node_id in node.neighbors:
                raise ValueError(f"Erro: O no {node_id} possui uma conexão para ele mesmo.")
            
            # Regra 2: Nós não podem estar vazios
            if not node.resources:
                raise ValueError(f"Erro: O no {node_id} não possui recursos.")
            
            # Regra 3: Limites de grau (min/max neighbors)
            degree = len(node.neighbors)
            if not (self.min_neighbors <= degree <= self.max_neighbors):
                raise ValueError(f"Erro: O no {node_id} tem {degree} vizinhos. Limite exigido: {self.min_neighbors} a {self.max_neighbors}.")
        
        # Regra 4: Rede não particionada (delegado ao algoritmo nativo em C do NetworkX)
        if not nx.is_connected(self.graph):
            raise ValueError("Erro: A rede está particionada. Existem nos isolados.")
            
        print(">> Validação concluída com sucesso: A topologia da rede atende a todos os requisitos.")
        return True

    def draw_topology_with_gui(self):
        """Renderiza o grafo e um painel lateral interativo para inserção dos parâmetros."""
        
        # Cria a janela principal
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.fig.canvas.manager.set_window_title('Simulador P2P')
        
        # Espreme o eixo principal (o grafo) para a direita para abrir espaço para o menu
        plt.subplots_adjust(left=0.35)
        
        # --- 1. RENDERIZAÇÃO DO GRAFO (No eixo direito) ---
        pos = nx.spring_layout(self.graph, seed=42) 
        nx.draw_networkx_edges(self.graph, pos, ax=self.ax, edge_color='#cccccc', width=2.0)
        nx.draw_networkx_nodes(self.graph, pos, ax=self.ax, node_color='skyblue', node_size=2000)

        id_labels = {n: n for n in self.nodes}
        resource_labels = {n: f"\n\n{obj.resources}" for n, obj in self.nodes.items()}
        
        nx.draw_networkx_labels(self.graph, pos, labels=id_labels, ax=self.ax, font_size=12, font_weight='bold')
        nx.draw_networkx_labels(self.graph, pos, labels=resource_labels, ax=self.ax, font_size=8, font_color='darkblue')
        
        self.ax.set_title("Topologia da Rede P2P", fontsize=16, fontweight='bold')
        self.ax.axis('off') 

        # --- 2. RENDERIZAÇÃO DO MENU LATERAL (Nos 35% da esquerda) ---
        
        # [Coordenada X, Coordenada Y, Largura, Altura] - Valores de 0.0 a 1.0
        ax_node = plt.axes([0.1, 0.75, 0.15, 0.05])
        self.txt_node = TextBox(ax_node, 'Node ID: ', initial='n1')
        
        ax_res = plt.axes([0.1, 0.65, 0.15, 0.05])
        self.txt_res = TextBox(ax_res, 'Recurso: ', initial='r20')
        
        ax_ttl = plt.axes([0.1, 0.55, 0.15, 0.05])
        self.txt_ttl = TextBox(ax_ttl, 'TTL: ', initial='4')
        
        ax_algo = plt.axes([0.05, 0.35, 0.25, 0.15])
        self.radio_algo = RadioButtons(ax_algo, ('flooding', 'informed_flooding', 'random_walk', 'informed_random_walk'))
        
        ax_btn = plt.axes([0.1, 0.2, 0.15, 0.08])
        self.btn_search = Button(ax_btn, 'INICIAR BUSCA', color='lightgreen', hovercolor='palegreen')

        # --- 3. MECÂNICA DE CALLBACK (Ação do Botão) ---
        def submit_search(event):
            # Coleta os valores digitados nas caixas de texto
            node = self.txt_node.text.strip()
            res = self.txt_res.text.strip()
            algo = self.radio_algo.value_selected
            
            try:
                ttl_val = int(self.txt_ttl.text.strip())
            except ValueError:
                print("\n[Erro na Interface] O campo TTL deve conter apenas números inteiros.")
                return
                
            print("\n" + "="*60)
            # Aciona a função central de busca que já tínhamos criado
            self.search(node_id=node, resource_id=res, ttl=ttl_val, algo=algo)
            print("="*60)

        # Conecta o clique do botão à função de execução
        self.btn_search.on_clicked(submit_search)
        
        # Remove a thread que criamos no main e exibe a tela normal
        plt.show()

    def search(self, node_id, resource_id, ttl, algo):
        """Interface central de busca e sistema de atualização de Cache."""
        if node_id not in self.nodes:
            print(f"\n[Erro] No de origem {node_id} não existe na rede.")
            return None

        print(f"\n[{algo.upper()}] Iniciando busca por '{resource_id}' a partir de {node_id} (TTL: {ttl})")

        stats = {
            'messages_exchanged': 0,
            'visited_nodes': set(),
            'found': False,
            'found_at': None
        }

        # Roteamento dos 4 algoritmos
        if algo == 'flooding':
            self._flooding(node_id, resource_id, ttl, stats)
        elif algo == 'random_walk':
            self._random_walk(node_id, resource_id, ttl, stats)
        elif algo == 'informed_flooding':
            self._informed_flooding(node_id, resource_id, ttl, stats)
        elif algo == 'informed_random_walk':
            self._informed_random_walk(node_id, resource_id, ttl, stats)
        else:
            print(f"Algoritmo '{algo}' não reconhecido.")
            return None

        # --- A MÁGICA DO CACHE ACONTECE AQUI ---
        # Se encontrou o recurso, todos os nós que participaram dessa busca "aprendem" a localização
        if stats['found']:
            target = stats['found_at']
            for v_node in stats['visited_nodes']:
                if v_node != target:
                    self.nodes[v_node].cache[resource_id] = target
            print(f"> [Sistema] Cache atualizado em {len(stats['visited_nodes'])} nos.")

        status = f"ENCONTRADO no no {stats['found_at']}" if stats['found'] else "FALHOU"
        print(f"> Resultado: {status}")
        print(f"> Mensagens trocadas: {stats['messages_exchanged']}")
        print(f"> Nos unicos visitados: {len(stats['visited_nodes'])}")
        
        return stats
    
    def _flooding(self, start_node, resource_id, ttl, stats):
        """Mecânica de Inundação com processamento concorrente e descarte por loop."""
        # A fila continua sendo nosso motor de paralelismo
        queue = [(start_node, ttl)]
        
        while queue:
            current_node, current_ttl = queue.pop(0)
            
            # 1. A DETECÇÃO DE LOOP: A mensagem chegou. O nó já viu essa busca antes?
            if current_node in stats['visited_nodes']:
                print(f"  -> [Loop Drop] No {current_node} descartou a mensagem (ja processada).")
                continue # Interrompe apenas esta ramificação, as outras continuam!
                
            # Se é a primeira vez, ele registra que viu a mensagem
            stats['visited_nodes'].add(current_node)
            node = self.nodes[current_node]
            print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")

            # 2. O SUCESSO: Achou o recurso, mas não mata a rede inteira
            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Encontrado em {current_node}! (As outras ramificaçoes continuam até o TTL zerar)")
                # Um nó que tem o recurso não repassa a busca para frente, mas o loop while continua
                continue

            if current_ttl <= 0:
                print(f"  -> [Drop] TTL zerado no no {current_node}.")
                continue

            # 3. A INUNDAÇÃO: Envia para TODOS os vizinhos cegamente. 
            # O custo da mensagem é cobrado aqui.
            for neighbor_id in node.neighbors:
                stats['messages_exchanged'] += 1
                queue.append((neighbor_id, current_ttl - 1))

    def _random_walk(self, start_node, resource_id, ttl, stats):
        """Mecânica de Passeio Aleatório com rastreamento de caminho e Backtracking."""
        # A pilha substitui a variável única de current_node
        path_stack = [start_node] 
        current_ttl = ttl
        
        # O nó inicial já é marcado para não receber a mensagem de volta logo no primeiro salto
        stats['visited_nodes'].add(start_node)
        
        while path_stack and current_ttl > 0:
            # Olha sempre para o topo da pilha (o nó onde a mensagem está agora)
            current_node = path_stack[-1]
            node = self.nodes[current_node]
            
            print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")

            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Recurso '{resource_id}' localizado em {current_node}!")
                return # No RW, o caminho é único, então achar o recurso finaliza a busca

            # Descobre quem são os vizinhos que ainda não viram essa mensagem
            valid_neighbors = [n for n in node.neighbors if n not in stats['visited_nodes']]
            
            if valid_neighbors:
                # O AVANÇO: Sorteia um caminho válido, consome recursos e empilha o novo nó
                next_node = random.choice(valid_neighbors)
                stats['visited_nodes'].add(next_node)
                stats['messages_exchanged'] += 1
                current_ttl -= 1
                
                path_stack.append(next_node)
                print(f"  -> [Avanço] Enviando de {current_node} para {next_node}")
            else:
                # O BACKTRACKING: Beco sem saída. Retira o nó inútil do topo da pilha.
                path_stack.pop() 
                
                # Se a pilha não ficou vazia, significa que podemos recuar para o nó anterior
                if path_stack:
                    previous_node = path_stack[-1]
                    stats['messages_exchanged'] += 1
                    current_ttl -= 1
                    print(f"  -> [Backtrack] Beco sem saída em {current_node}. Recuando para {previous_node}")

    def _informed_flooding(self, start_node, resource_id, ttl, stats):
        """Mecânica de Inundação Informada com paralelismo, descarte de loop e atalho de cache."""
        queue = [(start_node, ttl)]
        
        while queue:
            current_node, current_ttl = queue.pop(0)
            
            # 1. DETECÇÃO DE LOOP: Impede o processamento infinito da mesma mensagem
            if current_node in stats['visited_nodes']:
                print(f"  -> [Loop Drop] Nó {current_node} descartou a mensagem (já processada).")
                continue
                
            stats['visited_nodes'].add(current_node)
            node = self.nodes[current_node]
            print(f"  -> [Trace] Nó {current_node} processando (TTL: {current_ttl})")

            # 2. O ATALHO (BUSCA INFORMADA): Consulta o cache antes de inundar
            if resource_id in node.cache:
                target_node = node.cache[resource_id]
                stats['found'] = True
                stats['found_at'] = target_node
                stats['messages_exchanged'] += 1 # Custo de 1 mensagem para o salto direto
                print(f"  -> [Cache HIT] Nó {current_node} sabe que '{resource_id}' está em {target_node}! Salto direto executado.")
                continue # Permite que outras ramificações em voo continuem

            # 3. VERIFICAÇÃO LOCAL: O recurso está no próprio nó?
            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Recurso '{resource_id}' localizado fisicamente em {current_node}!")
                continue # Permite que outras ramificações continuem

            if current_ttl <= 0:
                print(f"  -> [Drop] TTL zerado no nó {current_node}.")
                continue

            # 4. A INUNDAÇÃO: Se não está no cache e nem localmente, espalha para os vizinhos
            for neighbor_id in node.neighbors:
                stats['messages_exchanged'] += 1
                queue.append((neighbor_id, current_ttl - 1))

    def _informed_random_walk(self, start_node, resource_id, ttl, stats):
        """Mecânica de Passeio Aleatório Informado com Backtracking e atalho de cache."""
        path_stack = [start_node] 
        current_ttl = ttl
        stats['visited_nodes'].add(start_node)
        
        while path_stack and current_ttl > 0:
            current_node = path_stack[-1]
            node = self.nodes[current_node]
            
            print(f"  -> [Trace] Nó {current_node} processando (TTL: {current_ttl})")

            # 1. O ATALHO (BUSCA INFORMADA): Consulta o cache primeiro
            if resource_id in node.cache:
                target_node = node.cache[resource_id]
                stats['found'] = True
                stats['found_at'] = target_node
                stats['messages_exchanged'] += 1
                print(f"  -> [Cache HIT] Nó {current_node} sabe que '{resource_id}' está em {target_node}! Salto direto executado.")
                return # No RW, como existe apenas um caminho, a busca acaba ao encontrar o recurso

            # 2. VERIFICAÇÃO LOCAL
            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Recurso '{resource_id}' localizado fisicamente em {current_node}!")
                return

            # 3. MAPEAMENTO DE CAMINHOS VÁLIDOS
            valid_neighbors = [n for n in node.neighbors if n not in stats['visited_nodes']]
            
            if valid_neighbors:
                # AVANÇO: Sorteia, consome TTL/mensagens e empilha
                next_node = random.choice(valid_neighbors)
                stats['visited_nodes'].add(next_node)
                stats['messages_exchanged'] += 1
                current_ttl -= 1
                
                path_stack.append(next_node)
                print(f"  -> [Avanço] Enviando de {current_node} para {next_node}")
            else:
                # BACKTRACKING: Beco sem saída, recua consumindo TTL/mensagens
                path_stack.pop() 
                if path_stack:
                    previous_node = path_stack[-1]
                    stats['messages_exchanged'] += 1
                    current_ttl -= 1
                    print(f"  -> [Backtrack] Beco sem saída em {current_node}. Recuando para {previous_node}")

def interactive_menu(p2p_network):
    """Gera uma interface interativa no terminal para o usuário rodar buscas seguidas."""
    print("\n" + "="*50)
    print("SISTEMA DE BUSCA P2P INTERATIVO".center(50))
    print("="*50)

    # Mapeamento para facilitar a digitação do usuário
    algo_map = {
        '1': 'flooding',
        '2': 'informed_flooding',
        '3': 'random_walk',
        '4': 'informed_random_walk'
    }

    while True:
        print("\n" + "-"*50)
        print("Nova Busca (Pressione ENTER no 'Node ID' para sair)")
        
        # 1. Input do Node ID
        node_id = input("1. Node ID de origem (ex: n1): ").strip()
        if not node_id:
            print("\nEncerrando o sistema P2P. Até logo!")
            break
            
        if node_id not in p2p_network.nodes:
            print("Erro: Este no não existe na rede. Tente novamente.")
            continue

        # 2. Input do Resource ID
        resource_id = input("2. Resource ID buscado (ex: r20): ").strip()

        # 3. Input do TTL com tratamento de erro
        try:
            ttl = int(input("3. TTL (Time to Live, ex: 4): ").strip())
        except ValueError:
            print("Erro: O TTL deve ser um número inteiro (ex: 3, 4, 5).")
            continue

        # 4. Input do Algoritmo
        print("\nAlgoritmos disponíveis:")
        print("  [1] flooding")
        print("  [2] informed_flooding")
        print("  [3] random_walk")
        print("  [4] informed_random_walk")
        
        algo_choice = input("4. Escolha o algoritmo (digite 1, 2, 3 ou 4): ").strip()

        if algo_choice not in algo_map and algo_choice not in algo_map.values():
            print("Erro: Escolha de algoritmo inválida.")
            continue
            
        # Se o usuário digitou '1', converte para 'flooding'. Se digitou 'flooding', mantém.
        algo = algo_map.get(algo_choice, algo_choice)

        # Executa a busca com os dados fornecidos
        print("\n" + "*"*30)
        p2p_network.search(node_id, resource_id, ttl, algo)
        print("*"*30)


if __name__ == "__main__":
    p2p = P2PNetwork()
    
    try:
        print("Carregando arquivo de configuraçao e validando...")
        p2p.load_from_json('rede_teste.json')
        p2p.validate_network()
        
        print("Abrindo simulador com painel lateral...")
        # Essa chamada agora segura o programa e renderiza tudo junto
        p2p.draw_topology_with_gui()
        
    except FileNotFoundError:
        print("Erro: O arquivo 'rede_teste.json' não foi encontrado.")
    except ValueError as err:
        print(err)