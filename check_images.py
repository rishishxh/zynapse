import os, pandas as pd

df = pd.read_csv('data/products.csv', nrows=10)
print("Sample ASINs from CSV:", df['asin'].tolist())

for asin in df['asin'].tolist():
    path = f'static/images/{asin}.jpg'
    print(f"  {path} -> exists: {os.path.exists(path)}")

print("placeholder.png:", os.path.exists('static/assets/placeholder.png'))
print("placeholder_product.png:", os.path.exists('static/assets/placeholder_product.png'))

# Check image folder sample
imgs = sorted(os.listdir('static/images'))[:10]
print("First 10 image files:", imgs)
