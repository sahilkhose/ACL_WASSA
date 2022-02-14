from jax import device_count
from dataloader import WASSADataset
from config import get_config, get_static_config
from utils import *
from model import *

import torch

cfg = get_config(
    remove_stopwords=False,
    lemmatize=False,
    maxlen=100,
    num_classes=7,
    batch_size=64,
    mode="train",
    classification_loss="categorical_crossentropy",
    regression_loss="mean_squared_error"
)

# dataloader = EssayDataloader(
#     './messages_train_ready_for_WS.tsv', cfg)

# essays = dataloader.get_track_1_inputs()
# labels = dataloader.get_track_1_outputs()

model = EssayToAllBERT(cfg)

ds = WASSADataset('./messages_train_ready_for_WS.tsv', cfg)

train_size = int(len(ds) * 0.8)
val_size = len(ds) - train_size

train_ds, val_ds = torch.utils.data.random_split(
    ds, [train_size, val_size])

train_ds = torch.utils.data.DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, drop_last=True)
val_ds = torch.utils.data.DataLoader(
    val_ds, batch_size=cfg.batch_size, shuffle=False, drop_last=True)

criteria = get_criteria(cfg)

optimizer = torch.optim.Adam(model.parameters(), lr=0.001)


def accuracy(true, pred):
    # print(type(true), type(pred))
    acc = (true == pred.argmax(-1)).float().detach().sum()
    return float(100 * acc / len(true))


def f1_loss(y_true: torch.Tensor, y_pred: torch.Tensor, is_training=False) -> torch.Tensor:
    '''Calculate F1 score. Can work with gpu tensors
    
    The original implmentation is written by Michal Haltuf on Kaggle.
    
    Returns
    -------
    torch.Tensor
        `ndim` == 1. 0 <= val <= 1
    
    Reference
    ---------
    - https://www.kaggle.com/rejpalcz/best-loss-function-for-f1-score-metric
    - https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html#sklearn.metrics.f1_score
    - https://discuss.pytorch.org/t/calculating-precision-recall-and-f1-score-in-case-of-multi-label-classification/28265/6
    
    '''
    assert y_true.ndim == 1
    assert y_pred.ndim == 1 or y_pred.ndim == 2

    if y_pred.ndim == 2:
        y_pred = y_pred.argmax(dim=1)

    tp = (y_true * y_pred).sum().to(torch.float32)
    tn = ((1 - y_true) * (1 - y_pred)).sum().to(torch.float32)
    fp = ((1 - y_true) * y_pred).sum().to(torch.float32)
    fn = (y_true * (1 - y_pred)).sum().to(torch.float32)

    epsilon = 1e-7

    precision = tp / (tp + fp + epsilon)
    recall = tp / (tp + fn + epsilon)

    f1 = 2 * (precision*recall) / (precision + recall + epsilon)
    f1.requires_grad = is_training
    return f1

device = torch.device(
    "cuda") if torch.cuda.is_available() else torch.device("cpu")


for epoch in range(3):
    print("Epoch:", epoch)
    epoch_loss = []
    epoch_acc = []
    for batchnum, batch in enumerate(train_ds):
        
        print("Batch:", batchnum)
        batch[0] = model.tokenizer(text=batch[0],
                                   add_special_tokens=True,
                                   return_attention_mask=True,
                                   max_length=cfg.maxlen,
                                   padding='max_length',
                                   truncation=True,
                                   return_tensors="pt")

        batch = [elem.to(device) for elem in batch]

        outputs = model(batch)
        
        loss = 0
        for i in range(len(outputs)):
            loss += criteria[i](outputs[i],batch[i+1])
        
        loss.backward()
        
        # loss
        optimizer.step()
        optimizer.zero_grad()

        acc = accuracy(batch[1], outputs[0])
        epoch_loss.append(loss)
        epoch_acc.append(acc)

        f1 = f1_loss(batch[1], outputs[0])

        print("Train loss: ", loss)
        print("Train accuracy: ", acc)
        print("Train F1:", f1)

    state = {
        'epoch': epoch,
        'state_dict': model.state_dict(),
        'optimizer': optimizer.state_dict(),
    }
    torch.save(state, f"./ckpts/bert_{epoch}.pt")

    model.eval()
    with torch.no_grad():
        for val_batch in val_ds:
            val_batch[0] = model.tokenizer(text=val_batch[0],
                                       add_special_tokens=True,
                                       return_attention_mask=True,
                                       max_length=cfg.maxlen,
                                       padding='max_length',
                                       truncation=True,
                                       return_tensors="pt")

            val_batch = [elem.to(device) for elem in val_batch]

            val_outputs = model(val_batch)
            val_loss = 0
            for i in range(len(val_outputs)):
                
                val_loss += criteria[i](val_outputs[i], val_batch[i+1]) 

            val_f1 = f1_loss(val_batch[1], val_outputs[0])
            print("Val loss: ", val_loss)
            print("val accuracy: ", accuracy(val_batch[1], val_outputs[0]))
            print("Val f1: ", val_f1)



# ----------------------------- OLD ------------------------------------------#
# input_ids, attn_masks = bb._prepare_input(essays)
# outputs = bb.forward(input_ids[:5], attn_masks[:5], labels[:5].unsqueeze(0))

# input_ids_ds = DataLoader(input_ids, shuffle=False, batch_size=8)
# attn_masks_ds = DataLoader(attn_masks, shuffle=False, batch_size=8)
# labels_ds = DataLoader(labels, shuffle=False, batch_size=8)

# train_ds = zip(input_ids_ds, attn_masks_ds, labels_ds)


# for batch in train_ds:
#     print(batch[0])
#     break


# def train(model, optimizer, train_dataloader):
#     device = torch.device(
#         "cuda") if torch.cuda.is_available() else torch.device("cpu")
#     model.to(device)
#     for epoch in range(3):
#         print("Epoch:", epoch)
#         for i, batch in enumerate(train_dataloader):
#             print("Batch:", i)
#             batch.to(device)
#             outputs = model(
#                 input_ids=batch[0], attention_mask=batch[1], labels=batch[2])
#             loss = outputs.loss
#             loss.backward()
#             optimizer.step()
#             optimizer.zero_grad()

#             print("Train loss: ", loss)


# train(bb.model, opt, train_ds)
# print(torch.nn.softmax(outputs.logits))
# print(outputs.loss)
