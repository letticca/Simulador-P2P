import json
import random
import networkx as nx
from collections import deque
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
            
        print(">> Validaçao concluída com sucesso: A topologia da rede atende a todos os requisitos.")
        return True

    def draw_topology_with_gui(self):
        """Renderiza o grafo e um painel lateral interativo para inserção dos parâmetros."""
        
        # Cria a janela principal
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.fig.canvas.manager.set_window_title('Simulador P2P')
        
        # Espreme o eixo principal (o grafo) para a direita para abrir espaço para o menu
        plt.subplots_adjust(left=0.35)
        
        #1. Renderizacao do grafo (No eixo direito) 
        pos = nx.spring_layout(self.graph, seed=42) 
        nx.draw_networkx_edges(self.graph, pos, ax=self.ax, edge_color='#cccccc', width=2.0)
        nx.draw_networkx_nodes(self.graph, pos, ax=self.ax, node_color='skyblue', node_size=2000)

        id_labels = {n: n for n in self.nodes}
        resource_labels = {n: f"\n\n{obj.resources}" for n, obj in self.nodes.items()}
        
        nx.draw_networkx_labels(self.graph, pos, labels=id_labels, ax=self.ax, font_size=12, font_weight='bold')
        nx.draw_networkx_labels(self.graph, pos, labels=resource_labels, ax=self.ax, font_size=8, font_color='darkblue')
        
        self.ax.set_title("Topologia da Rede P2P", fontsize=16, fontweight='bold')
        self.ax.axis('off') 

        # 2. Renderizacao do Menu na lateral
        
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
            self.search(node_id=node, resource_id=res, ttl=ttl_val, algo=algo)
            print("="*60)

        # Conecta o clique do botão à função de execução
        self.btn_search.on_clicked(submit_search)
        
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

        # Cache
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
        """Mecanica de Inundacao (BFS) otimizada com deque e marcacao antecipada."""
        # CORREÇÃO: A fila agora guarda (no_atual, ttl_atual, no_pai)
        queue = deque([(start_node, ttl, None)])
        stats['visited_nodes'].add(start_node)
        
        while queue:
            current_node, current_ttl, parent_node = queue.popleft()
            node = self.nodes[current_node]
            print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")

            # 1. Verificacao de sucesso
            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Recurso '{resource_id}' localizado em {current_node}!")
                continue

            # 2. Verificacao de TTL 
            if current_ttl <= 0:
                print(f"  -> [Drop] TTL zerado no no {current_node}.")
                continue

            # 3. Inundacao
            for neighbor_id in node.neighbors:
                # CORREÇÃO: Se o vizinho for quem enviou a mensagem, ignore-o completamente
                if neighbor_id == parent_node:
                    continue

                if neighbor_id not in stats['visited_nodes']:
                    print(f"  -> [Propagacao] No {current_node} envia mensagem para o No {neighbor_id}")
                    stats['visited_nodes'].add(neighbor_id)
                    stats['messages_exchanged'] += 1
                    # O current_node passa a ser o parent_node da próxima iteração
                    queue.append((neighbor_id, current_ttl - 1, current_node))
                else:
                    print(f"  -> [Descarte] No {current_node} enviou para {neighbor_id}, mas {neighbor_id} ja foi visitado. Nao propaga.")

    def _informed_flooding(self, start_node, resource_id, ttl, stats):
        """Mecanica de Inundacao Informada com otimizacao de deque e atalho de cache."""
        # CORREÇÃO: A fila agora guarda (no_atual, ttl_atual, no_pai)
        queue = deque([(start_node, ttl, None)])
        stats['visited_nodes'].add(start_node)
        
        while queue:
            current_node, current_ttl, parent_node = queue.popleft()
            node = self.nodes[current_node]
            print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")

            # 1. Atalho de Cache
            if resource_id in node.cache:
                target_node = node.cache[resource_id]
                stats['found'] = True
                stats['found_at'] = target_node
                stats['messages_exchanged'] += 1 
                print(f"  -> [Cache HIT] No {current_node} redireciona busca diretamente para {target_node}!")
                continue

            # 2. Verificacao Local
            if resource_id in node.resources:
                stats['found'] = True
                stats['found_at'] = current_node
                print(f"  -> [Sucesso] Recurso '{resource_id}' localizado fisicamente em {current_node}!")
                continue

            # 3.Verificacao TTL
            if current_ttl <= 0:
                print(f"  -> [Drop] TTL zerado no no {current_node}.")
                continue

            # 4. Propagacao
            for neighbor_id in node.neighbors:
                # CORREÇÃO: Se o vizinho for quem enviou a mensagem, ignore-o completamente
                if neighbor_id == parent_node:
                    continue

                if neighbor_id not in stats['visited_nodes']:
                    print(f"  -> [Propagacao] No {current_node} envia mensagem para o No {neighbor_id}")
                    stats['visited_nodes'].add(neighbor_id)
                    stats['messages_exchanged'] += 1
                    queue.append((neighbor_id, current_ttl - 1, current_node))
                else:
                    print(f"  -> [Descarte] No {current_node} enviou para {neighbor_id}, mas {neighbor_id} ja foi visitado. Nao propaga.")
    def _random_walk(self, start_node, resource_id, ttl, stats):
        """Mecânica de Passeio Aleatório (DFS Limitado) com Backtracking e Raio de Profundidade."""
        # A pilha agora guarda o estado do nó E o TTL disponível naquele momento
        path_stack = [(start_node, ttl)] 
        stats['visited_nodes'].add(start_node)
        
        # Memória para não reprocessar o recurso do nó na volta do backtrack
        processed_nodes = set()

        while path_stack:
            # Observa o topo da pilha (Nó atual e quanto TTL ele tem)
            current_node, current_ttl = path_stack[-1]
            node = self.nodes[current_node]
            
            # 1. INSPEÇÃO: Consulta os recursos apenas na primeira vez que passa aqui
            if current_node not in processed_nodes:
                print(f"  -> [Trace] Nó {current_node} processando (TTL: {current_ttl})")
                processed_nodes.add(current_node)

                if resource_id in node.resources:
                    stats['found'] = True
                    stats['found_at'] = current_node
                    print(f"  -> [Sucesso] Recurso '{resource_id}' localizado em {current_node}!")
                    return

            # 2. VERIFICAÇÃO DE TTL: Limite de profundidade atingido para este ramo
            if current_ttl <= 0:
                print(f"  -> [Drop] Limite de profundidade (TTL=0) atingido em {current_node}. Recuando.")
                path_stack.pop() # Remove este nó inútil da pilha
                continue         # Volta para o início do laço (que agora lerá o pai com o TTL preservado)

            # 3. MAPEAMENTO: Descobre quem são os vizinhos ainda não visitados na rede
            valid_neighbors = [n for n in node.neighbors if n not in stats['visited_nodes']]
            
            if valid_neighbors:
                # AVANÇO: Sorteia um caminho, consome 1 de TTL e empilha
                next_node = random.choice(valid_neighbors)
                stats['visited_nodes'].add(next_node)
                stats['messages_exchanged'] += 1
                
                path_stack.append((next_node, current_ttl - 1))
                print(f"  -> [Avanço] Enviando de {current_node} para {next_node}")
            else:
                # BACKTRACKING FÍSICO: Não há mais vizinhos. O pacote avisa o pai e recua.
                path_stack.pop() 
                
                if path_stack:
                    previous_node, _ = path_stack[-1]
                    stats['messages_exchanged'] += 1
                    print(f"  -> [Backtrack] Beco sem saída em {current_node}. Recuando para {previous_node}")

    def _random_walk(self, start_node, resource_id, ttl, stats):
        """Mecanica de Passeio Aleatorio (DFS Limitado) com Backtracking e Raio de Profundidade."""
        # A pilha agora guarda o estado do no E o TTL disponivel naquele momento
        path_stack = [(start_node, ttl)] 
        stats['visited_nodes'].add(start_node)
        
        # Memoria para nao reprocessar o recurso do no na volta do backtrack
        processed_nodes = set()

        while path_stack:
            # Observa o topo da pilha (No atual e quanto TTL ele tem)
            current_node, current_ttl = path_stack[-1]
            node = self.nodes[current_node]
            
            # 1. INSPECAO: Consulta os recursos apenas na primeira vez que passa aqui
            if current_node not in processed_nodes:
                print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")
                processed_nodes.add(current_node)

                if resource_id in node.resources:
                    stats['found'] = True
                    stats['found_at'] = current_node
                    print(f"  -> [Sucesso] Recurso '{resource_id}' localizado em {current_node}!")
                    return

            # 2. VERIFICACAO DE TTL: Limite de profundidade atingido para este ramo
            if current_ttl <= 0:
                print(f"  -> [Drop] Limite de profundidade (TTL=0) atingido em {current_node}. Recuando.")
                path_stack.pop() # Remove este no inutil da pilha
                continue         # Volta para o inicio do laco (que agora lera o pai com o TTL preservado)

            # 3. MAPEAMENTO: Descobre quem sao os vizinhos ainda nao visitados na rede
            valid_neighbors = [n for n in node.neighbors if n not in stats['visited_nodes']]
            
            if valid_neighbors:
                # AVANCO: Sorteia um caminho, consome 1 de TTL e empilha
                next_node = random.choice(valid_neighbors)
                stats['visited_nodes'].add(next_node)
                stats['messages_exchanged'] += 1
                
                path_stack.append((next_node, current_ttl - 1))
                print(f"  -> [Avanco] Enviando de {current_node} para {next_node}")
            else:
                # BACKTRACKING FISICO: Nao ha mais vizinhos. O pacote avisa o pai e recua.
                path_stack.pop() 
                
                if path_stack:
                    previous_node, _ = path_stack[-1]
                    stats['messages_exchanged'] += 1
                    print(f"  -> [Backtrack] Beco sem saida em {current_node}. Recuando para {previous_node}")

    def _informed_random_walk(self, start_node, resource_id, ttl, stats):
        """Mecanica de Passeio Aleatorio Informado (DFS Limitado) com Backtracking e atalho de cache."""
        path_stack = [(start_node, ttl)] 
        stats['visited_nodes'].add(start_node)
        processed_nodes = set()
        
        while path_stack:
            current_node, current_ttl = path_stack[-1]
            node = self.nodes[current_node]
            
            # 1. INSPECAO
            if current_node not in processed_nodes:
                print(f"  -> [Trace] No {current_node} processando (TTL: {current_ttl})")
                processed_nodes.add(current_node)

                # Cache
                if resource_id in node.cache:
                    target_node = node.cache[resource_id]
                    stats['found'] = True
                    stats['found_at'] = target_node
                    stats['messages_exchanged'] += 1
                    print(f"  -> [Cache HIT] No {current_node} sabe que '{resource_id}' esta em {target_node}! Salto direto executado.")
                    return 

                # Recursos Locais
                if resource_id in node.resources:
                    stats['found'] = True
                    stats['found_at'] = current_node
                    print(f"  -> [Sucesso] Recurso '{resource_id}' localizado fisicamente em {current_node}!")
                    return

            # 2. VERIFICACAO DE TTL
            if current_ttl <= 0:
                print(f"  -> [Drop] Limite de profundidade (TTL=0) atingido em {current_node}. Recuando.")
                path_stack.pop()
                continue

            # 3. MAPEAMENTO
            valid_neighbors = [n for n in node.neighbors if n not in stats['visited_nodes']]
            
            if valid_neighbors:
                # AVANCO
                next_node = random.choice(valid_neighbors)
                stats['visited_nodes'].add(next_node)
                stats['messages_exchanged'] += 1
                
                path_stack.append((next_node, current_ttl - 1))
                print(f"  -> [Avanco] Enviando de {current_node} para {next_node}")
            else:
                # BACKTRACKING
                path_stack.pop() 
                if path_stack:
                    previous_node, _ = path_stack[-1]
                    stats['messages_exchanged'] += 1
                    print(f"  -> [Backtrack] Beco sem saida em {current_node}. Recuando para {previous_node}")


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
        p2p.draw_topology_with_gui()
        
    except FileNotFoundError:
        print("Erro: O arquivo 'rede_teste.json' não foi encontrado.")
    except ValueError as err:
        print(err)