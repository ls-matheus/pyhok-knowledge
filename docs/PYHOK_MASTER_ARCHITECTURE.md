# PyHok & Sinapse Engine
## Master Document — Arquitetura, Visão e Propósito

**Projeto:** PyHok & Sinapse Engine
**Paradigma:** Local-First Cognitive Engine with Synthetic Epistemic Evolution
**Documento:** Master Architecture & Product Vision
**Versão:** 1.0

---

# 1. PROPÓSITO DESTE DOCUMENTO

Este documento define a identidade arquitetural e a visão fundamental do ecossistema PyHok.

Ele responde:

- O que é o PyHok?
- Qual problema o PyHok pretende resolver?
- O que é o Sinapse Engine?
- O que é o PyHok Knowledge?
- Como essas partes se relacionam?
- Onde acontece a execução?
- Onde acontece a construção de conhecimento?
- Quais são os limites fundamentais do sistema?

Este documento representa a visão arquitetural do projeto.

Ele não define:

- como um agente de IA deve raciocinar;
- quais alterações um agente pode realizar;
- quais propostas devem ser aceitas;
- quais critérios de validação devem ser aplicados em uma execução específica.

Essas responsabilidades pertencem às demais camadas da arquitetura epistemológica do repositório.

---

# 2. O QUE É O PYHOK?

O PyHok é um ecossistema cognitivo e de suporte sensório-motor de alta performance projetado para pessoas neurodivergentes.

Seu princípio arquitetural fundamental é:

> **Local-First / Edge-Heavy.**

Isso significa que o processamento tático, a interpretação determinística dos sinais e as decisões operacionais de segurança devem ocorrer localmente no dispositivo.

O sistema não deve depender de uma conexão com a internet para executar suas funções críticas de tempo real.

O PyHok separa explicitamente:

1. processamento determinístico local;
2. representação computável de conhecimento;
3. evolução sintética do conhecimento;
4. síntese de linguagem natural.

Essa separação existe para reduzir:

- latência;
- dependência de rede;
- custo operacional;
- exposição desnecessária de dados;
- risco de uma IA generativa controlar funções críticas.

---

# 3. AS DUAS IDENTIDADES DO ECOSSISTEMA

O ecossistema possui duas identidades principais.

## 3.1 PyHok — Experiência e Persona

O PyHok representa a experiência do usuário.

Sua interface é construída em Flutter e possui como elemento central a mascote Coruja.

A interface deve ser acolhedora, responsiva e capaz de adaptar sua apresentação às necessidades observadas pelo sistema.

A experiência visual pode adaptar dinamicamente:

- contraste;
- quantidade de elementos;
- cores;
- ritmo;
- complexidade visual;
- intensidade das intervenções.

A interface não deve possuir autoridade própria para interpretar sinais críticos ou determinar estados operacionais.

Ela apresenta e responde às decisões produzidas pelo núcleo determinístico.

---

# 4. SINAPSE ENGINE — NÚCLEO DETERMINÍSTICO

O Sinapse Engine é o núcleo computacional determinístico do ecossistema.

Ele é implementado em C++20 e pode operar no dispositivo através de:

- execução nativa;
- Dart FFI;
- WebAssembly.

Sua responsabilidade é processar sinais e executar avaliações determinísticas.

O núcleo local é responsável por:

1. receber sinais;
2. normalizar sinais;
3. calcular ou atualizar baselines locais;
4. avaliar hipóteses computáveis;
5. calcular evidências;
6. ponderar qualidade dos sinais;
7. combinar evidências;
8. aplicar relações do conhecimento;
9. estimar estados;
10. calcular confiança e incerteza;
11. executar a Policy Engine;
12. produzir o estado operacional utilizado pela interface.

O Sinapse não deve depender de uma LLM para executar decisões críticas em tempo real.

---

# 5. PYHOK KNOWLEDGE — LABORATÓRIO EPISTÊMICO

O `pyhok-knowledge` é o repositório responsável pela representação e evolução do conhecimento utilizado pelo ecossistema.

Ele não é:

- um banco de frases;
- um sistema de diagnóstico;
- um coletor de telemetria infantil;
- um sistema de execução;
- um substituto do Sinapse Engine.

Ele é uma rede estruturada de conhecimento sobre padrões observacionais relacionados à interação humana, cognição, atenção, dinâmica motora, carga sensorial, fadiga, estresse, autonomia, comunicação e suas relações temporais e multimodais.

O repositório funciona como um:

> **Laboratório Epistêmico Autônomo.**

Seu objetivo é permitir que a estrutura de conhecimento seja refinada continuamente sem conceder autoridade operacional ao agente responsável por sua evolução.

---

# 6. PRINCÍPIO FUNDAMENTAL DE OBSERVAÇÃO

O PyHok não deve partir da ideia de que um único sinal identifica uma condição.

O sistema deve partir de observações.

A lógica fundamental é:

> **observar → representar → combinar evidências → preservar incerteza → adaptar suporte.**

Uma observação isolada não deve ser tratada automaticamente como uma explicação completa.

O objetivo é permitir que o sistema compreenda melhor:

- o que está acontecendo;
- como o padrão se comporta;
- em quais condições ele aparece;
- como ele muda ao longo do tempo;
- quais outras observações o reforçam;
- quais observações o contradizem;
- quando a evidência é insuficiente.

---

# 7. VARIABILIDADE INDIVIDUAL

O comportamento humano possui grande variabilidade individual.

Por isso, o PyHok não deve assumir que um determinado comportamento possui o mesmo significado para todas as pessoas.

Um padrão motor que representa alteração para uma pessoa pode representar comportamento habitual para outra.

O Sinapse utiliza uma linha de base local adaptativa para representar o comportamento individual.

Consequentemente:

> o sistema deve comparar observações principalmente com o contexto individual disponível, e não tratar padrões populacionais abstratos como verdade universal.

A evolução do conhecimento também deve respeitar esse princípio.

Uma hipótese útil deve ser formulada de maneira compatível com variabilidade individual e incerteza.

---

# 8. SINAIS

Os sinais representam observações produzidas pelo ambiente ou pela interação do usuário com o dispositivo.

Exemplos de sinais incluem:

## Interação motora

- velocidade do cursor;
- aceleração;
- variância da trajetória;
- latência de clique;
- pausas na digitação;
- características temporais do movimento.

## Atenção ocular e facial

Quando esses sinais estiverem disponíveis e forem suportados pelo sistema:

- duração de fixação;
- frequência de mudanças de foco;
- movimento da cabeça;
- características de movimento facial.

## Sinais derivados

O sistema pode representar características temporais derivadas, como:

- média móvel;
- variância;
- taxa de alteração;
- persistência;
- desvio relativo à baseline.

Um sinal é uma observação.

Ele não é, por si só, uma explicação causal.

---

# 9. QUALIDADE DA OBSERVAÇÃO

Cada evidência deve preservar a qualidade do sinal que a originou.

Representa-se essa qualidade por:

Q(i,t) ∈ [0,1]

Quando a qualidade de uma observação é insuficiente, a observação não deve ser transformada artificialmente em evidência negativa.

O princípio é:

> **ausência de evidência não é evidência de ausência.**

Formalmente:

E_tilde(i,t) = E(i,t) × Q(i,t)

Assim, quando:

Q(i,t) = 0

a evidência utilizável é anulada, mas isso não significa que o fenômeno observado seja falso.

---

# 10. QUESTION ENTITY

Uma `QuestionEntity` representa uma hipótese computável.

Ela não é simplesmente uma pergunta textual apresentada ao usuário.

É uma estrutura que descreve uma relação observacional que o Sinapse pode avaliar utilizando sinais e métodos existentes.

Uma hipótese pode representar, por exemplo:

> "Existe alteração temporal no padrão motor compatível com hesitação?"

Essa hipótese somente é válida para execução quando estiver vinculada a:

- sinais existentes;
- métodos de avaliação existentes;
- contratos conhecidos pelo Sinapse;
- critérios computáveis;
- contexto temporal apropriado.

Uma hipótese não deve criar automaticamente novos sensores, métodos ou capacidades de execução.

---

# 11. MÉTODOS DE AVALIAÇÃO

Uma hipótese pode utilizar métodos de avaliação conhecidos pelo Sinapse.

Exemplos:

- threshold;
- baseline deviation;
- persistence.

O método transforma observações em uma força de evidência:

E(i,t) ∈ [0,1]

A existência de uma hipótese no conhecimento não implica que ela seja executada.

A hipótese precisa ser compatível com o catálogo de métodos e com o contrato do núcleo.

---

# 12. RELATION GRAPH

O conhecimento do PyHok não é apenas uma coleção de hipóteses independentes.

As hipóteses podem possuir relações estruturais.

Relações possíveis incluem:

- `REINFORCES`
- `CONTRADICTS`
- `REQUIRES`
- `SUPERSEDES`

Essas relações representam como diferentes evidências devem ser interpretadas em conjunto.

O grafo deve permitir representar:

- complementaridade;
- conflito;
- dependência;
- substituição;
- interação temporal;
- interação entre diferentes modalidades observacionais.

O significado de uma hipótese deve ser considerado dentro do grafo quando relações relevantes existirem.

---

# 13. EVOLUÇÃO DO CONHECIMENTO

O PyHok Knowledge possui um agente de IA responsável por analisar a estrutura existente e identificar oportunidades de evolução.

O ciclo conceitual é:

~~~text
Conhecimento atual
       │
       ▼
Análise estrutural
       │
       ▼
Identificação de lacunas
       │
       ▼
Proposição de evolução
       │
       ▼
Validação
       │
       ▼
Mudança controlada
       │
       ▼
Novo estado do conhecimento
~~~

A evolução pode envolver:

- novas hipóteses;
- atualização de hipóteses;
- novas relações;
- refinamento estrutural.

O agente não deve evoluir o sistema por mera produção de conteúdo.

Uma mudança somente possui valor quando melhora a capacidade representacional do conhecimento sem introduzir inconsistência ou redundância desnecessária.

---

# 14. O AGENTE NÃO É O SISTEMA

O agente de IA é um componente auxiliar do laboratório epistemológico.

Ele não é:

- o Sinapse Engine;
- a Policy Engine;
- a autoridade operacional do dispositivo;
- uma fonte absoluta de verdade;
- um sistema de diagnóstico.

O agente analisa e propõe.

O restante do sistema valida.

Essa separação é fundamental.

---

# 15. ESTEIRA DE VALIDAÇÃO

Toda evolução proposta pelo agente deve passar por validação antes de integrar o conhecimento oficial.

A validação deve verificar, entre outras propriedades:

- validade estrutural;
- compatibilidade de schema;
- existência dos sinais referenciados;
- existência dos métodos utilizados;
- coerência das relações;
- compatibilidade com a missão;
- ausência de violações de regras;
- ausência de conflitos proibidos;
- preservação das propriedades existentes.

A IA não deve ser considerada suficiente para validar a própria alteração.

---

# 16. DATASET E DISTRIBUIÇÃO

O conhecimento consolidado pode ser publicado como dataset versionado.

Um release representa um estado validado do conhecimento.

O cliente local pode receber esse dataset e validar sua integridade antes de utilizá-lo.

A distribuição deve preservar:

- versionamento;
- integridade;
- compatibilidade;
- possibilidade de rollback.

O dataset não deve modificar o kernel de execução.

---

# 17. SINAPSE — PIPELINE OPERACIONAL

O pipeline conceitual do Sinapse é:

~~~text
Sinais
  │
  ▼
Normalização / Baseline
  │
  ▼
Question Evaluation
  │
  ▼
Evidence
  │
  ▼
Quality Weighting
  │
  ▼
Evidence Fusion
  │
  ▼
Relation Graph
  │
  ▼
State Estimation
  │
  ▼
Confidence / Uncertainty
  │
  ▼
Policy Engine
  │
  ▼
Interface
~~~

O conhecimento fornece estruturas para interpretação.

O Sinapse fornece execução determinística.

---

# 18. ESTADO LATENTE

O sistema pode representar um estado operacional através de dimensões latentes.

Entre as dimensões utilizadas pela arquitetura atual estão:

- Foco;
- Estresse;
- Autonomia;
- Fadiga.

Essas dimensões não devem ser interpretadas como diagnósticos.

Elas representam estados operacionais utilizados para orientar o comportamento do sistema.

A estimativa deve preservar:

- evidência;
- confiança;
- incerteza;
- temporalidade;
- variabilidade individual.

---

# 19. CONFIANÇA E INCERTEZA

A confiança representa o quanto o estado atual é sustentado por evidências disponíveis e confiáveis.

Representa-se:

C(t) ∈ [0,1]

e:

U(t) = 1 - C(t)

Alta incerteza deve limitar decisões operacionais.

O sistema deve preferir não agir a agir com falsa certeza quando as evidências disponíveis forem insuficientes.

---

# 20. POLICY ENGINE

A Policy Engine é uma máquina de estados finitos executada localmente.

Seu papel é transformar estados e evidências suficientemente confiáveis em comportamento operacional da interface.

Estados conceituais incluem:

~~~text
NORMAL
   │
   ▼
SUPPORT
   │
   ▼
MITIGATION
   │
   ▼
RECOVERY
   │
   ▼
NORMAL
~~~

As transições devem utilizar persistência temporal e histerese para evitar mudanças bruscas provocadas por flutuações momentâneas.

---

# 21. INVARIANTES DE SEGURANÇA

O ecossistema deve preservar cinco propriedades fundamentais.

## P1 — Histerese de transição

Estados não devem sofrer saltos bruscos causados por uma única observação momentânea.

## P2 — Trava de incerteza

Alta incerteza deve impedir alterações operacionais que dependam de confiança suficiente.

## P3 — Recuperação

O sistema deve possuir caminhos claros e reversíveis de retorno ao estado normal.

## P4 — Reversibilidade

Intervenções de interface devem poder ser desfeitas.

## P5 — Isolamento da nuvem

A nuvem não possui autoridade para:

- alterar a Policy Engine;
- executar código nativo;
- modificar o estado operacional;
- contornar o Sinapse;
- assumir controle do dispositivo.

---

# 22. DUPLO DUCTO

O ecossistema possui dois fluxos distintos.

## Foreground

O caminho crítico de interação.

~~~text
Sinal
  ↓
Sinapse
  ↓
Estado
  ↓
Policy
  ↓
Interface
~~~

Esse caminho deve permanecer local e determinístico.

## Background

O caminho de evolução e armazenamento.

~~~text
Knowledge Dataset
       ↓
Cache local
       ↓
Aplicação
~~~

Esse fluxo não deve bloquear a execução crítica.

---

# 23. RELAÇÃO ENTRE AS PRINCIPAIS PARTES

A arquitetura pode ser resumida assim:

~~~text
                  ┌──────────────────────────┐
                  │       MASTER VISION      │
                  │       O que é o PyHok?   │
                  └────────────┬─────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │    PYHOK KNOWLEDGE  │          │    SINAPSE ENGINE   │
   │                     │          │                     │
   │ Conhecimento        │          │ Execução             │
   │ Hipóteses           │─────────▶│ determinística       │
   │ Relações            │ Dataset  │                     │
   │ Métodos             │          │ Sinais              │
   │ Evolução            │          │ Evidências           │
   └──────────┬──────────┘          │ Estados              │
              │                     │ Policy               │
              │                     └──────────┬──────────┘
              │                                │
              │                                ▼
              │                     ┌─────────────────────┐
              │                     │       PYHOK         │
              │                     │     Flutter/UI      │
              │                     └─────────────────────┘
              │
              ▼
      Agente de Conhecimento
      + Validação + Releases
~~~

---

# 24. SEPARAÇÃO FUNDAMENTAL DE AUTORIDADE

A arquitetura estabelece uma separação explícita:

| Componente | Responsabilidade |
|---|---|
| PyHok UI | Experiência e apresentação |
| Sinapse Engine | Execução determinística |
| Knowledge Graph | Representação do conhecimento |
| Knowledge Agent | Análise e proposição |
| Validation Pipeline | Validação das mudanças |
| Cloud LLM | Síntese linguística |
| Policy Engine | Decisão operacional local |

Nenhum componente deve assumir silenciosamente a responsabilidade de outro.

---

# 25. PRINCÍPIO CENTRAL DO ECOSSISTEMA

O PyHok deve buscar compreender padrões antes de agir sobre eles.

A arquitetura segue o princípio:

~~~text
OBSERVAR
   ↓
REPRESENTAR
   ↓
CONTEXTUALIZAR
   ↓
COMBINAR EVIDÊNCIAS
   ↓
MEDIR CONFIANÇA
   ↓
PRESERVAR INCERTEZA
   ↓
ADAPTAR SUPORTE
~~~

A finalidade não é transformar pessoas em classificações.

A finalidade é construir um sistema capaz de perceber padrões individuais, representar hipóteses computáveis sobre esses padrões e adaptar o suporte de maneira segura, reversível e contextual.

---

# 26. LIMITE ARQUITETURAL ABSOLUTO

O conhecimento pode evoluir.

O grafo pode crescer.

As hipóteses podem ser refinadas.

As relações podem se tornar mais sofisticadas.

Mas a evolução do conhecimento não concede automaticamente novas capacidades ao runtime.

Em particular:

> **Evoluir conhecimento não significa evoluir autoridade operacional.**

O Knowledge Graph pode descrever novas hipóteses.

O agente pode propor novas estruturas.

A validação pode aceitar uma mudança.

Ainda assim, o Sinapse somente executará aquilo que seu contrato determinístico suporta.

Essa separação constitui uma das propriedades fundamentais de segurança do PyHok.
