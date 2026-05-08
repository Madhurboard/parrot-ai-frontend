from PIL import Image
import os

# Open the logo
img = Image.open('public/logo.png')

# Resize to favicon size
img_resized = img.resize((64, 64), Image.Resampling.LANCZOS)

# Save as ICO
img_resized.save('public/favicon.ico')
print('✅ Favicon created successfully!')
print('Size: ' + str(os.path.getsize('public/favicon.ico')) + ' bytes')
