// Seed Concepts
MERGE (c1:Concept {id: 'c-linear-algebra'})
ON CREATE SET c1.name = 'Linear Algebra', c1.description = 'Vectors, matrices, linear transforms, and vector spaces.', c1.difficulty_level = 'Beginner';

MERGE (c2:Concept {id: 'c-calculus'})
ON CREATE SET c2.name = 'Calculus', c2.description = 'Limits, derivatives, integrals, and approximation methods.', c2.difficulty_level = 'Beginner';

MERGE (c3:Concept {id: 'c-probability-stats'})
ON CREATE SET c3.name = 'Probability & Statistics', c3.description = 'Random variables, distributions, Bayes rule, and estimations.', c3.difficulty_level = 'Beginner';

MERGE (c4:Concept {id: 'c-matrix-operations'})
ON CREATE SET c4.name = 'Matrix Operations', c4.description = 'Matrix addition, multiplication, inversion, and determinants.', c4.difficulty_level = 'Beginner';

MERGE (c5:Concept {id: 'c-partial-derivatives'})
ON CREATE SET c5.name = 'Partial Derivatives', c5.description = 'Derivatives of multi-variable functions with respect to single variables.', c5.difficulty_level = 'Beginner';

MERGE (c6:Concept {id: 'c-chain-rule'})
ON CREATE SET c6.name = 'Chain Rule', c6.description = 'Formula for computing the derivative of the composition of two or more functions.', c6.difficulty_level = 'Beginner';

MERGE (c7:Concept {id: 'c-bayes-theorem'})
ON CREATE SET c7.name = 'Bayes Theorem', c7.description = 'Mathematical formula for determining conditional probabilities.', c7.difficulty_level = 'Beginner';

MERGE (c8:Concept {id: 'c-loss-function'})
ON CREATE SET c8.name = 'Loss Function', c8.description = 'Function that maps values of variables onto a real number representing cost.', c8.difficulty_level = 'Beginner';

MERGE (c9:Concept {id: 'c-gradient-descent'})
ON CREATE SET c9.name = 'Gradient Descent', c9.description = 'Optimization algorithm to minimize loss by moving in steepest descent direction.', c9.difficulty_level = 'Intermediate';

MERGE (c10:Concept {id: 'c-sgd'})
ON CREATE SET c10.name = 'Stochastic Gradient Descent', c10.description = 'Iterative method for optimizing objective functions using sample subsets.', c10.difficulty_level = 'Intermediate';

MERGE (c11:Concept {id: 'c-optimization'})
ON CREATE SET c11.name = 'Optimization', c11.description = 'Selecting the best element with regard to some criteria from alternatives.', c11.difficulty_level = 'Intermediate';

MERGE (c12:Concept {id: 'c-neural-networks'})
ON CREATE SET c12.name = 'Neural Networks', c12.description = 'Computational models inspired by biological brains to recognize patterns.', c12.difficulty_level = 'Intermediate';

MERGE (c13:Concept {id: 'c-activation-functions'})
ON CREATE SET c13.name = 'Activation Functions', c13.description = 'Functions defining output of a node given inputs.', c13.difficulty_level = 'Intermediate';

MERGE (c14:Concept {id: 'c-backpropagation'})
ON CREATE SET c14.name = 'Backpropagation', c14.description = 'Algorithm for supervised learning of neural nets using gradient chain rule.', c14.difficulty_level = 'Intermediate';

MERGE (c15:Concept {id: 'c-regularization'})
ON CREATE SET c15.name = 'Regularization', c15.description = 'Introducing information/constraints to prevent overfitting.', c15.difficulty_level = 'Intermediate';

MERGE (c16:Concept {id: 'c-sigmoid-relu'})
ON CREATE SET c16.name = 'Sigmoid & ReLU', c16.description = 'Common non-linear activation functions used to enable deep learning representation.', c16.difficulty_level = 'Beginner';

MERGE (c17:Concept {id: 'c-feedforward-networks'})
ON CREATE SET c17.name = 'Feedforward Networks', c17.description = 'The simplest type of artificial neural network where connections do not form cycles.', c17.difficulty_level = 'Intermediate';

MERGE (c18:Concept {id: 'c-cnns'})
ON CREATE SET c18.name = 'Convolutional Neural Networks (CNNs)', c18.description = 'Deep learning models designed for processing grid structured data like images.', c18.difficulty_level = 'Advanced';

MERGE (c19:Concept {id: 'c-rnns'})
ON CREATE SET c19.name = 'Recurrent Neural Networks (RNNs)', c19.description = 'Neural networks where connections form a directed graph along a temporal sequence.', c19.difficulty_level = 'Advanced';

MERGE (c20:Concept {id: 'c-lstms'})
ON CREATE SET c20.name = 'LSTM & GRU', c20.description = 'Recurrent neural network architectures designed to learn long-term dependencies.', c20.difficulty_level = 'Advanced';

MERGE (c21:Concept {id: 'c-seq2seq'})
ON CREATE SET c21.name = 'Sequence to Sequence', c21.description = 'Models mapping variable-length input sequences to variable-length outputs.', c21.difficulty_level = 'Advanced';

MERGE (c22:Concept {id: 'c-attention'})
ON CREATE SET c22.name = 'Attention Mechanism', c22.description = 'Technique dynamically focusing on specific parts of inputs during output generation.', c22.difficulty_level = 'Advanced';

MERGE (c23:Concept {id: 'c-self-attention'})
ON CREATE SET c23.name = 'Self-Attention', c23.description = 'Attention mechanism relating different positions of a sequence to compute its representation.', c23.difficulty_level = 'Advanced';

MERGE (c24:Concept {id: 'c-multi-head-attention'})
ON CREATE SET c24.name = 'Multi-Head Attention', c24.description = 'Running self-attention multiple times in parallel to project inputs into different subspaces.', c24.difficulty_level = 'Advanced';

MERGE (c25:Concept {id: 'c-transformers'})
ON CREATE SET c25.name = 'Transformers', c25.description = 'Deep learning architecture relying solely on attention mechanisms for sequence processing.', c25.difficulty_level = 'Advanced';

MERGE (c26:Concept {id: 'c-positional-encoding'})
ON CREATE SET c26.name = 'Positional Encoding', c26.description = 'Injecting order/positional information to tokens since attention is permutation-invariant.', c26.difficulty_level = 'Advanced';

MERGE (c27:Concept {id: 'c-gnns'})
ON CREATE SET c27.name = 'Graph Neural Networks (GNNs)', c27.description = 'Neural networks designed to perform inference on graph-structured data.', c27.difficulty_level = 'Advanced';

MERGE (c28:Concept {id: 'c-gcns'})
ON CREATE SET c28.name = 'Graph Convolutional Networks (GCNs)', c28.description = 'Type of graph neural network utilizing spectral or spatial convolutions.', c28.difficulty_level = 'Advanced';

MERGE (c29:Concept {id: 'c-llms'})
ON CREATE SET c29.name = 'Large Language Models', c29.description = 'Generative models trained on massive text corpora to perform language tasks.', c29.difficulty_level = 'Advanced';

MERGE (c30:Concept {id: 'c-bert-gpt'})
ON CREATE SET c30.name = 'BERT & GPT', c30.description = 'Pioneering encoder/decoder transformer models for language representation and generation.', c30.difficulty_level = 'Advanced';

// Seed Papers
MERGE (p1:Paper {id: 'p-attention'})
ON CREATE SET p1.title = 'Attention Is All You Need', p1.year = 2017, p1.doi = '10.48550/arXiv.1706.03762', p1.abstract = 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.';

MERGE (p2:Paper {id: 'p-resnet'})
ON CREATE SET p2.title = 'Deep Residual Learning for Image Recognition', p2.year = 2015, p2.doi = '10.1109/CVPR.2016.90', p2.abstract = 'Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those previously used.';

MERGE (p3:Paper {id: 'p-gcn'})
ON CREATE SET p3.title = 'Semi-Supervised Classification with Graph Convolutional Networks', p3.year = 2016, p3.doi = '10.48550/arXiv.1609.02907', p3.abstract = 'We present a scalable approach for semi-supervised learning on graph-structured data that is based on an efficient variant of convolutional neural networks which operate directly on graphs.';

MERGE (p4:Paper {id: 'p-adam'})
ON CREATE SET p4.title = 'Adam: A Method for Stochastic Optimization', p4.year = 2014, p4.doi = '10.48550/arXiv.1412.6980', p4.abstract = 'We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions, based on adaptive estimates of lower-order moments.';

MERGE (p5:Paper {id: 'p-gan'})
ON CREATE SET p5.title = 'Generative Adversarial Nets', p5.year = 2014, p5.doi = '10.48550/arXiv.1406.2661', p5.abstract = 'We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model and a discriminative model.';

// Seed Authors
MERGE (a1:Author {id: 'a-ashish-vaswani'}) ON CREATE SET a1.name = 'Ashish Vaswani';
MERGE (a2:Author {id: 'a-kaiming-he'}) ON CREATE SET a2.name = 'Kaiming He';
MERGE (a3:Author {id: 'a-thomas-kipf'}) ON CREATE SET a3.name = 'Thomas Kipf';
MERGE (a4:Author {id: 'a-diederik-kingma'}) ON CREATE SET a4.name = 'Diederik P. Kingma';
MERGE (a5:Author {id: 'a-ian-goodfellow'}) ON CREATE SET a5.name = 'Ian Goodfellow';

// Seed Institutions
MERGE (inst:Institution {id: 'inst-google'}) ON CREATE SET inst.name = 'Google Research', inst.country = 'United States';

// Seed Relationships
// Prerequisite links
MATCH (c_la:Concept {id: 'c-linear-algebra'}), (c_mo:Concept {id: 'c-matrix-operations'}) MERGE (c_la)-[:PREREQUISITE_OF]->(c_mo);
MATCH (c_la:Concept {id: 'c-linear-algebra'}), (c_gd:Concept {id: 'c-gradient-descent'}) MERGE (c_la)-[:PREREQUISITE_OF]->(c_gd);
MATCH (c_calc:Concept {id: 'c-calculus'}), (c_pd:Concept {id: 'c-partial-derivatives'}) MERGE (c_calc)-[:PREREQUISITE_OF]->(c_pd);
MATCH (c_pd:Concept {id: 'c-partial-derivatives'}), (c_cr:Concept {id: 'c-chain-rule'}) MERGE (c_pd)-[:PREREQUISITE_OF]->(c_cr);
MATCH (c_cr:Concept {id: 'c-chain-rule'}), (c_bp:Concept {id: 'c-backpropagation'}) MERGE (c_cr)-[:PREREQUISITE_OF]->(c_bp);
MATCH (c_prob:Concept {id: 'c-probability-stats'}), (c_bt:Concept {id: 'c-bayes-theorem'}) MERGE (c_prob)-[:PREREQUISITE_OF]->(c_bt);
MATCH (c_bt:Concept {id: 'c-bayes-theorem'}), (c_reg:Concept {id: 'c-regularization'}) MERGE (c_bt)-[:PREREQUISITE_OF]->(c_reg);
MATCH (c_loss:Concept {id: 'c-loss-function'}), (c_gd:Concept {id: 'c-gradient-descent'}) MERGE (c_loss)-[:PREREQUISITE_OF]->(c_gd);
MATCH (c_gd:Concept {id: 'c-gradient-descent'}), (c_sgd:Concept {id: 'c-sgd'}) MERGE (c_gd)-[:PREREQUISITE_OF]->(c_sgd);
MATCH (c_gd:Concept {id: 'c-gradient-descent'}), (c_nn:Concept {id: 'c-neural-networks'}) MERGE (c_gd)-[:PREREQUISITE_OF]->(c_nn);
MATCH (c_mo:Concept {id: 'c-matrix-operations'}), (c_nn:Concept {id: 'c-neural-networks'}) MERGE (c_mo)-[:PREREQUISITE_OF]->(c_nn);
MATCH (c_nn:Concept {id: 'c-neural-networks'}), (c_af:Concept {id: 'c-activation-functions'}) MERGE (c_nn)-[:PREREQUISITE_OF]->(c_af);
MATCH (c_af:Concept {id: 'c-activation-functions'}), (c_sr:Concept {id: 'c-sigmoid-relu'}) MERGE (c_af)-[:PREREQUISITE_OF]->(c_sr);
MATCH (c_sr:Concept {id: 'c-sigmoid-relu'}), (c_ff:Concept {id: 'c-feedforward-networks'}) MERGE (c_sr)-[:PREREQUISITE_OF]->(c_ff);
MATCH (c_bp:Concept {id: 'c-backpropagation'}), (c_ff:Concept {id: 'c-feedforward-networks'}) MERGE (c_bp)-[:PREREQUISITE_OF]->(c_ff);
MATCH (c_ff:Concept {id: 'c-feedforward-networks'}), (c_cnn:Concept {id: 'c-cnns'}) MERGE (c_ff)-[:PREREQUISITE_OF]->(c_cnn);
MATCH (c_ff:Concept {id: 'c-feedforward-networks'}), (c_rnn:Concept {id: 'c-rnns'}) MERGE (c_ff)-[:PREREQUISITE_OF]->(c_rnn);
MATCH (c_rnn:Concept {id: 'c-rnns'}), (c_lstm:Concept {id: 'c-lstms'}) MERGE (c_rnn)-[:PREREQUISITE_OF]->(c_lstm);
MATCH (c_lstm:Concept {id: 'c-lstms'}), (c_s2s:Concept {id: 'c-seq2seq'}) MERGE (c_lstm)-[:PREREQUISITE_OF]->(c_s2s);
MATCH (c_s2s:Concept {id: 'c-seq2seq'}), (c_att:Concept {id: 'c-attention'}) MERGE (c_s2s)-[:PREREQUISITE_OF]->(c_att);
MATCH (c_att:Concept {id: 'c-attention'}), (c_sa:Concept {id: 'c-self-attention'}) MERGE (c_att)-[:PREREQUISITE_OF]->(c_sa);
MATCH (c_sa:Concept {id: 'c-self-attention'}), (c_mha:Concept {id: 'c-multi-head-attention'}) MERGE (c_sa)-[:PREREQUISITE_OF]->(c_mha);
MATCH (c_mha:Concept {id: 'c-multi-head-attention'}), (c_tx:Concept {id: 'c-transformers'}) MERGE (c_mha)-[:PREREQUISITE_OF]->(c_tx);
MATCH (c_pe:Concept {id: 'c-positional-encoding'}), (c_tx:Concept {id: 'c-transformers'}) MERGE (c_pe)-[:PREREQUISITE_OF]->(c_tx);
MATCH (c_tx:Concept {id: 'c-transformers'}), (c_gnn:Concept {id: 'c-gnns'}) MERGE (c_tx)-[:PREREQUISITE_OF]->(c_gnn);
MATCH (c_tx:Concept {id: 'c-transformers'}), (c_llm:Concept {id: 'c-llms'}) MERGE (c_tx)-[:PREREQUISITE_OF]->(c_llm);
MATCH (c_gnn:Concept {id: 'c-gnns'}), (c_gcn:Concept {id: 'c-gcns'}) MERGE (c_gnn)-[:PREREQUISITE_OF]->(c_gcn);
MATCH (c_llm:Concept {id: 'c-llms'}), (c_bg:Concept {id: 'c-bert-gpt'}) MERGE (c_llm)-[:PREREQUISITE_OF]->(c_bg);

// Related and extends links
MATCH (c_cnn:Concept {id: 'c-cnns'}), (c_gnn:Concept {id: 'c-gnns'}) MERGE (c_cnn)-[:RELATED_TO]->(c_gnn);
MATCH (c_mo:Concept {id: 'c-matrix-operations'}), (c_pd:Concept {id: 'c-partial-derivatives'}) MERGE (c_mo)-[:RELATED_TO]->(c_pd);
MATCH (c_sgd:Concept {id: 'c-sgd'}), (c_opt:Concept {id: 'c-optimization'}) MERGE (c_sgd)-[:RELATED_TO]->(c_opt);
MATCH (c_bp:Concept {id: 'c-backpropagation'}), (c_reg:Concept {id: 'c-regularization'}) MERGE (c_bp)-[:RELATED_TO]->(c_reg);

// Paper relationships to concepts
MATCH (p:Paper {id: 'p-attention'}), (c:Concept {id: 'c-transformers'}) MERGE (p)-[:USES_METHOD]->(c);
MATCH (p:Paper {id: 'p-resnet'}), (c:Concept {id: 'c-cnns'}) MERGE (p)-[:USES_METHOD]->(c);
MATCH (p:Paper {id: 'p-gcn'}), (c:Concept {id: 'c-gcns'}) MERGE (p)-[:USES_METHOD]->(c);
MATCH (p:Paper {id: 'p-adam'}), (c:Concept {id: 'c-sgd'}) MERGE (p)-[:USES_METHOD]->(c);
MATCH (p:Paper {id: 'p-gan'}), (c:Concept {id: 'c-neural-networks'}) MERGE (p)-[:USES_METHOD]->(c);

// Citation relations (cites)
MATCH (p1:Paper {id: 'p-gcn'}), (p2:Paper {id: 'p-attention'}) MERGE (p1)-[:CITES]->(p2);

// Author relationships to papers
MATCH (p:Paper {id: 'p-attention'}), (a:Author {id: 'a-ashish-vaswani'}) MERGE (p)-[:AUTHORED_BY]->(a);
MATCH (p:Paper {id: 'p-resnet'}), (a:Author {id: 'a-kaiming-he'}) MERGE (p)-[:AUTHORED_BY]->(a);
MATCH (p:Paper {id: 'p-gcn'}), (a:Author {id: 'a-thomas-kipf'}) MERGE (p)-[:AUTHORED_BY]->(a);
MATCH (p:Paper {id: 'p-adam'}), (a:Author {id: 'a-diederik-kingma'}) MERGE (p)-[:AUTHORED_BY]->(a);
MATCH (p:Paper {id: 'p-gan'}), (a:Author {id: 'a-ian-goodfellow'}) MERGE (p)-[:AUTHORED_BY]->(a);

// Author affiliations
MATCH (a:Author {id: 'a-ashish-vaswani'}), (inst:Institution {id: 'inst-google'}) MERGE (a)-[:AFFILIATED_WITH]->(inst);
