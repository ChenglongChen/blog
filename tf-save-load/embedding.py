import os, time
import tensorflow as tf

dir = os.path.dirname(os.path.realpath(__file__))
results_dir = dir + "/results/" + str(int(time.time()))

### UTILS ###
def batch_text(corpus, batch_size, seq_length):
    if seq_length >= len(corpus):
        raise Error("seq_length >= len(corpus): %d>=%d" % (seq_length, len(corpus)))

    seqs = [corpus[i:i+seq_length] for i in range(len(corpus) - seq_length)]
    ys = [corpus[i:i+1] for i in range(seq_length, len(corpus))]
    for i in range(0, len(seqs), batch_size):
        x = seqs[i:i+batch_size]
        y = ys[i:i+batch_size]

        yield x, y

        
# Let's take a usual usecase you might have:
# You want to train a NN on a NLP task but first you want to train an embedding on your corpus to maximise your result (arguing about the fact that word embedding are better/worst than character solutions is beyond the scope of this article)
# This lead you to create

# here is our corpus
with open("lorem.txt", 'r') as f:
    text = f.read()
corpus = text.split()
corpus_length = len(corpus)
# let's create an embedding
# first let's build our dictrionnariesa nd count how namy unique word (token) we have:
tokens = set(corpus)
word_to_id_dict = { word:i for i, word in enumerate(tokens) }
id_to_word_dict = { i:word for word,i in word_to_id_dict.items() }
id_corpus = [ word_to_id_dict[word] for word in corpus ]
nb_token = len(tokens)

# This will be our first dimension, then we will choose (this is an hyper parameter) in how many dimensions we want to mebed our words
# For the sake of this blog post, let's keep it very simple and chose 30
dim_embedding = 30

# We decide to predict the next word thanks only to its previous word
seq_length = 5

# We will train this embedding with the most simple prior we can: a word is dependant on the previous one
# So the input of our model is a word and the output is the id of next word
with tf.variable_scope("placeholder"):
    x = tf.placeholder(tf.int32, shape=[None, seq_length], name="x")
    y_true = tf.placeholder(tf.int32, shape=[None, 1], name="y_true")

with tf.variable_scope("embedding"):
    # Let's build our embedding, we intialize it with s impel random normal centerd on 0 with a small variance
    embedding = tf.get_variable("embedding", shape=[nb_token, dim_embedding], initializer=tf.random_normal_initializer(0., 1e-3))
    # Then we retrieve the context vector
    context_vec = tf.nn.embedding_lookup(embedding, x, name="lookup") # Dim: bs x seq_length x dim_embedding
    context_vec = tf.reshape(context_vec, [tf.shape(x)[0], seq_length * dim_embedding])

with tf.variable_scope("1layer"):
    # We use the context vector to predict the next word vector inside the embedding
    W1 = tf.get_variable("W1", dtype=tf.float32, shape=[seq_length * dim_embedding, dim_embedding])
    b1 = tf.get_variable("b1", dtype=tf.float32, shape=[dim_embedding], initializer=tf.constant_initializer(.1))
    h1 = tf.nn.relu(tf.matmul(context_vec, W1) + b1)

    W2 = tf.get_variable("W2", dtype=tf.float32, shape=[dim_embedding, dim_embedding])
    b2 = tf.get_variable("b2", dtype=tf.float32, shape=[dim_embedding], initializer=tf.constant_initializer(.1))
    y_vector = tf.matmul(h1, W2) + b2 # Dim: bs x dim_embeddiing 

    # Now we calculated the dot product of the current words with all other words
    z = tf.matmul(y_vector, tf.transpose(embedding)) # Dim: bs x nb_token

with tf.variable_scope("loss"):
    y_true_reshaped = tf.reshape(y_true, [-1])
    losses = tf.nn.sparse_softmax_cross_entropy_with_logits(None, y_true_reshaped, z)
    loss_op = tf.reduce_mean(losses)

    tf.summary.scalar('loss', loss_op)

with tf.variable_scope("Accuracy"):
    a = tf.nn.softmax(z)
    predictions = tf.cast(tf.argmax(a, 1, name="predictions"), tf.int32)
    correct_predictions = tf.equal(predictions, y_true_reshaped)
    nb_predicted_words = tf.shape(predictions)[0]
    nb_wrong_predictions = nb_predicted_words - tf.reduce_sum(tf.cast(correct_predictions, tf.int32))
    accuracy = tf.reduce_mean(tf.cast(correct_predictions, tf.float32), name="accuracy")

with tf.variable_scope('Optimizer'):
    global_step_t = tf.Variable(0, name="global_step", trainable=False)
    lr = tf.train.exponential_decay(3e-2, global_step_t, 500, 0.5, staircase=True)
    adam = tf.train.AdamOptimizer(lr)
    tf.summary.scalar('lr', lr)
    
    train_op = adam.minimize(loss_op, global_step=global_step_t, name="train_op")

    summaries = tf.summary.merge_all()


saver = tf.train.Saver()
# We are going to use a helper function to create our inputs and labels
# The ptb_iterator is just a helper shifiting all the words by one and returning
# seq_length words for you to predict the next output
# very handy for RNN or our case
nb_epochs = 500
with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    sw = tf.summary.FileWriter(results_dir, sess.graph)

    for i in range(nb_epochs):
        input_gen = batch_text(id_corpus, corpus_length // 6, seq_length)
        for x_batch, y_true_batch in input_gen:
            to_compute = [train_op, loss_op, global_step_t, summaries]
            feed_dict = {
                x: x_batch,
                y_true: y_true_batch
            }
            _, loss, global_step, summaries_metric = sess.run(to_compute, feed_dict=feed_dict)

            sw.add_summary(summaries_metric, global_step)

        if (i + 1) % 250 == 0:
            saver.save(sess, results_dir + '/model', global_step=i + 1)

    # We compute the final accuracy
    val_gen = batch_text(id_corpus, corpus_length, seq_length)
    for x_batch, y_batch in val_gen:
        feed_dict = {
            x: x_batch,
            y_true: y_batch
        }
        acc, nb_preds, nb_w_pred = sess.run([accuracy, nb_predicted_words, nb_wrong_predictions], feed_dict=feed_dict)
        print('Final accuracy: %f' % acc)
        print('%d mispredicted words of %d predictions' % (nb_w_pred, nb_preds))

