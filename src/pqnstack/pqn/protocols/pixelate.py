import sys
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from matplotlib.widgets import Button
import os
from PIL import Image

def pixelate_image(p, img_path):
    """
    Pixelate an image, with `p = 0` showing the original image and `p = 1` reducing it to a single pixel.
    
    Args:
        p (float): Pixelation level, between 0 (no pixelation) and 1 (max pixelation).
        img_path (str): Path to the input image.

    Returns:
        np.ndarray: The pixelated image as a numpy array.
    """
    img = mpimg.imread(img_path)
    h, w = img.shape[:2]

    p = max(0, min(p, 1))

    scale_factor = 1 - p
    downscale_size = (
        max(1, int(h * scale_factor)),
        max(1, int(w * scale_factor)),
    )

    downscaled = Image.fromarray((img * 255).astype(np.uint8)).resize(
        (downscale_size[1], downscale_size[0]), resample=Image.NEAREST
    )
    pixelated_img = downscaled.resize((w, h), resample=Image.NEAREST)

    return np.array(pixelated_img) / 255.0

if __name__=='__main__':
    from PIL import Image
    fig,ax=plt.subplots()
    fig.canvas.manager.set_window_title('Pixelation Demo')
    img_path = os.path.expanduser('~/Downloads/Smiley.png')
    current_p=0.0
    shown_img=mpimg.imread(img_path)
    implot=ax.imshow(shown_img)
    def on_key(event):
        global current_p,shown_img
        if event.key in ['0','1','2','3','4','5', '6', '7', '8', '9']:
            lvl=int(event.key)
            current_p=lvl*0.0005 + 0.95
            shown_img=pixelate_image(current_p,img_path)
            implot.set_data(shown_img)
            plt.draw()
    fig.canvas.mpl_connect('key_press_event',on_key)
    plt.show()

