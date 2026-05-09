import pandas as pd
import numpy as np
import os

print("Loading raw products...")
df = pd.read_csv('data/products_raw.csv')
print(f"Loaded {len(df)} rows.")

# Find appropriate columns based on what exists
if 'display name' in df.columns:
    df['title'] = df['display name']
elif 'productDisplayName' in df.columns:
    df['title'] = df['productDisplayName']

if 'category' in df.columns:
    df['categoryName'] = df['category']
elif 'masterCategory' in df.columns:
    df['categoryName'] = df['masterCategory']

if 'id' in df.columns:
    df['asin'] = df['id'].astype(str)
elif 'image' in df.columns:
    df['asin'] = df['image'].astype(str).str.replace('.jpg', '', regex=False)

# Drop nulls
print("Dropping NA...")
df = df.dropna(subset=['asin', 'title', 'categoryName'])


print("Removing products containing 'bra'...")
df = df[~df['title'].str.contains(r'\bbra\b', case=False, na=False)]

# Keep only 10,000 rows
if len(df) > 10000:
    df = df.sample(10000, random_state=42).reset_index(drop=True)
else:
    df = df.reset_index(drop=True)
    
print(f"Kept {len(df)} rows.")

# Add required fields
print("Adding fields...")
np.random.seed(42)
df['price'] = np.random.uniform(500, 5000, size=len(df)).round(2)
df['boughtInLastMonth'] = np.random.randint(50, 1000, size=len(df))
df['stars'] = np.random.uniform(3.5, 5.0, size=len(df)).round(1)
df['isBestSeller'] = df['stars'] > 4.5

# Select final columns
final_cols = ['asin', 'title', 'categoryName', 'price', 'boughtInLastMonth', 'stars', 'isBestSeller']
df = df[final_cols]

df.to_csv('data/products.csv', index=False)
print("Saved data/products.csv")

# Clean old data if exists
if os.path.exists('data/demand.csv'):
    os.remove('data/demand.csv')
    print("Removed demand.csv")
if os.path.exists('data/old_products.csv'):
    os.remove('data/old_products.csv')
    print("Removed old products.csv")

# Ensure image paths in static/images
if not os.path.exists('static/images'):
    os.makedirs('static/images', exist_ok=True)
