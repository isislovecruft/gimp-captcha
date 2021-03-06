#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#NOTE!: the interpreter line above MUST run whichever python version
#your installation's gimp-python support is compiled with. ensure that this
#corresponds, or nothing here will work.

'''A Command Line Interface for Captcha Generation with Gimp

To use this script, place it in a gimp plug-ins directory and make it
executable. On Ubuntu Edgy this can be: $HOME/.gimp-2.2/plug-ins/

Invoke gimp like so:

    gimp --no-interface --no-data --console-messages \
        --batch '(python-fu-captcha-generate 1 "DIRECTORY" NUMBER) (gimp-quit 1)'

NUMBER is the number of captchas to put in the directory specified by
DIRECTORY. The directory will be "filled" to the goal level with pngs named
like ANSWER.jpg, where ANSWER is the string pictured in the image.
'''

from tempfile import mkstemp

import os
import random
import sys

import gimpfu
import gimpplugin

from gimpfu import gimp
from gimpfu import pdb as gpdb
from gimpfu import RGB_IMAGE
from gimpfu import GRAY_IMAGE
from gimpfu import GRAY
from gimpfu import NORMAL_MODE
from gimpfu import MULTIPLY_MODE
from gimpfu import WHITE_FILL
from gimpfu import TRANSPARENT_FILL
from gimpfu import FALSE
from gimpfu import PIXELS
from gimpfu import HISTOGRAM_VALUE
from gimpfu import CLIP_TO_IMAGE

from gimpenums import PLUGIN
from gimpenums import EXTENSION

# ==========
#  Settings
# ==========

# Units are generally in pixels:
CAPTCHA_LETTERS = 8
CAPTCHA_WIDTH   = 400
CAPTCHA_HEIGHT  = 125
FONT_HEIGHT     = 80
LEFT_MARGIN     = 10

# Remove characters to reduce confusion. No l, or o, for instance, as running
# them together might look like b or d.
CAPTCHA_CHARS   = 'aAbdeEfFgGjJknNMpPqQstTuvxyYzZ2479'
LETTER_SPACING  = -12
# Rotate individual letters, in radians:
ANGLE_RANGE     = (-0.30, 0.25)

FONTS = ['Sans', 'Serif', 'Monospace', 'Serif Bold', 'Century Schoolbook',
         'DejaVu Sans', 'DejaVu Sans Bold', 'FreeMono', 'FreeSerif']

# The extension of the file type to save generated CAPTCHAs as. Can be ".png"
# or ".jpg".
CAPTCHA_FILE_EXT = ".jpg"

# =============================================================================
#  End of settings (you probably don't want to touch anything further down)
# =============================================================================

PNG_INTERLACE   = 0
PNG_COMPRESSION = 9
PNG_BKGD        = 0
PNG_GAMA        = 0
PNG_OFFSET      = 0
PNG_PHYS        = 0
PNG_TIME        = 0
PNG_COMMENT     = 1
PNG_SVGTRANS    = 0

JPG_QUALITY     = float(1)
JPG_SMOOTHING   = float(0)
JPG_OPTIMIZE    = 0
JPG_PROGRESSIVE = 0
JPG_COMMENT     = ""
JPG_SUBSMP      = 0
JPG_BASELINE    = 1
JPG_MARKERS     = 0
JPG_DCTALGO     = 0


def make_captcha(sx, sy, font_height, letter_spacing, left_margin,
                 angle_range, fonts, answer):
    """Generate a captcha consisting of the letters in answer.

    :rtype: :class:`gimp.Image`
    :returns: The CAPTCHA as a gimp-python image object.
    """
    img = gimp.Image(sx, sy, RGB_IMAGE)
    img.disable_undo()

    light_noise_layer = gimp.Layer(img, 'light noise', sx, sy,
                                   RGB_IMAGE, 100, NORMAL_MODE)
    img.add_layer(light_noise_layer, 0)

    gpdb.gimp_selection_none(img)
    gpdb.gimp_drawable_fill(light_noise_layer, WHITE_FILL)

    # plug_in_randomize_hurl at 1% 1 time is vastly superior to
    # scatter_rgb here, but has a bug where it creates an artifact at
    # the top of the image when invoked in a scripting context like
    # this.
    #
    # Future experiment: dial down the amount of noise generated by
    # scatter, then run it through levels to darken it, then
    # blur. This should be equivalent to hurl + blur.
    #gpdb.plug_in_randomize_hurl(img, light_noise_layer, 1, 1, 0, 0)
    gpdb.plug_in_scatter_hsv(img, light_noise_layer, 1, 25, 200, 180)
    gpdb.plug_in_gauss_iir(img, light_noise_layer, 1, 1, 1)
    gpdb.gimp_desaturate(light_noise_layer)

    # Next make pure black layer which we will copy repeatedly as a
    # place to cut out letters.
    blackLayer = gimp.Layer(img, 'black', sx, sy, RGB_IMAGE, 100, NORMAL_MODE)
    img.add_layer(blackLayer, 0)
    blackLayer.add_alpha()
    gpdb.gimp_layer_add_alpha(blackLayer)
    gpdb.gimp_drawable_fill(blackLayer, WHITE_FILL)
    gpdb.gimp_invert(blackLayer)

    # Loop through each letter, making it a separate black layer.
    right = left_margin
    last_substrate = None
    for letter in answer:
        font = random.choice(FONTS)
        substrate = blackLayer.copy()
        img.add_layer(substrate, 0)
        new_right = cookie_cutter_letter(img, substrate, right, font, letter)
        # look out for really narrow letters
        if new_right - right < 20:
            new_right += 5
        right = new_right
    img.remove_layer(blackLayer)

    # Hide the light noise layer, then collapse all the remaining
    # layers (all letters) into a single layer.
    light_noise_layer.visible = False
    textLayer = gpdb.gimp_image_merge_visible_layers(img, CLIP_TO_IMAGE)
    light_noise_layer.visible = True

    # Create a layer of dark noise which will display the letters.
    dark_noise_layer = gimp.Layer(img, 'dark noise', sx, sy,
                                  RGB_IMAGE, 100, MULTIPLY_MODE)
    img.add_layer(dark_noise_layer, 1)
    gpdb.gimp_drawable_fill(dark_noise_layer, WHITE_FILL)
    gpdb.plug_in_randomize_hurl(img, dark_noise_layer, 25, 1, 0, 0)
    gpdb.gimp_desaturate(dark_noise_layer)

    # These next operations are ordered carefully. Changing the order
    # dramatically affects how the output looks.

    # Here's where we do the cutout operation.
    gpdb.gimp_selection_layer_alpha(textLayer)
    gpdb.gimp_selection_invert(img)
    gpdb.gimp_edit_clear(dark_noise_layer)
    gpdb.gimp_selection_none(img)

    # After the cutout, blur the dark noise layer and then darken it:
    gpdb.plug_in_gauss_iir(img, dark_noise_layer, 1, 1, 1)
    gpdb.gimp_levels(dark_noise_layer, HISTOGRAM_VALUE, 127, 255, 0.25, 0, 255)
    textLayer.visible = False

    # If you start gimp without --no-interface with an X server, this
    # line will let you see the image looks like at this point in the
    # script, layers and all. It should be fine to move this line to
    # any problematic part of the script for debugging.
    #
    # gimp.Display(gpdb.gimp_image_duplicate(img))

    final = img.flatten()
    gpdb.gimp_image_clean_all(img)
    img.enable_undo()
    return img, final

def cookie_cutter_letter(img, substrate, right, font, letter):
    '''Cut text shaped like letter out of the given layer.'''

    temp_layer = gpdb.gimp_text_fontname(img, substrate, right, 0, letter,
                                         1, False, FONT_HEIGHT, PIXELS, font)
    gpdb.gimp_selection_layer_alpha(temp_layer)

    angle = random.uniform(*ANGLE_RANGE)
    xaxis = right
    yaxis = 15
    # srcX = float(xaxis)
    # dstX = float(srcX + random.uniform(0, 25))
    # srcY = float(yaxis)
    # dstY = float(srcY + random.uniform(0, 25))
    # scaleX = scaleY = float(100)

    # We need to save the selection as a channel so we can mess with
    # the letter form.
    shape = gpdb.gimp_selection_save(img)
    gpdb.gimp_selection_none(img)
    gpdb.gimp_floating_sel_remove(temp_layer)

    # Distort the form of the individual letter:
    shape = gpdb.gimp_item_transform_rotate(shape, angle, 0, xaxis, yaxis)

    # We aren't doing any letter warping now, but if we were, this is the
    # point where it should be done. We want to warp the shape of textLayer,
    # which later serves as a cutout for the dark noise layer. If we warp the
    # dark noise layer directly we will end up with warped dots.
    #
    # gpdb.gimp_context_set_transform_resize(TRANSFORM_RESIZE_CROP)
    # shape = gpdb.gimp_item_transform_2d(shape, srcX, srcY, angle,
    #                                     scaleX, scaleY, dstX, dstY)
    gpdb.gimp_selection_load(shape)
    img.remove_channel(shape)

    # Note the bounding box of the letter form so we can figure out
    # where the next one should go.
    bounds = gpdb.gimp_selection_bounds(img)
    new_right = bounds[3] + LETTER_SPACING

    # Actually cut the letter form out of the substate.
    gpdb.gimp_selection_invert(img)
    gpdb.gimp_edit_clear(substrate)
    gpdb.gimp_selection_none(img)
    return new_right

def selectAnswer(length):
    """Select **length** charaters to form a CAPTCHA answer string.

    The alphabet is chosen to contain fewew similar letter shapes in roman
    fonts.

    :param int length: The number of letters to use for each CAPTCHA answer.
    :rtype: str
    :returns: A randomish string which can be made into a CAPTCHA.
    """
    answerLetters = []
    for letter in random.sample(CAPTCHA_CHARS, length):
        answerLetters.append(letter)
    answer = ''.join(answerLetters)
    return answer

def countImages(imageDir):
    """Count the images with the given file extension in a directory."""
    return len([f for f in os.listdir(imageDir)
                if f.endswith(CAPTCHA_FILE_EXT)])

def captcha_generate(imageDir, goal):
    """Make sure there are as many catchas in image_dir as goal."""
    needed = goal - countImages(imageDir)
    if needed < 1:
        return

    answers = [selectAnswer(CAPTCHA_LETTERS) for i in xrange(0, needed)]
    for answer in answers:
        imageFile = '{0}{1}'.format(answer, CAPTCHA_FILE_EXT)
        imagePath = os.path.join(imageDir, imageFile)
        imageTmp  = '%s.tmp' % imagePath

        img, drawable = make_captcha(CAPTCHA_WIDTH, CAPTCHA_HEIGHT,
                                     FONT_HEIGHT, LETTER_SPACING, LEFT_MARGIN,
                                     ANGLE_RANGE, FONTS, answer)

        try:
            if CAPTCHA_FILE_EXT == ".jpg":
                gpdb.file_jpeg_save(img, drawable,
                                    imageTmp, imageTmp,
                                    JPG_QUALITY,
                                    JPG_SMOOTHING,
                                    JPG_OPTIMIZE,
                                    JPG_PROGRESSIVE,
                                    JPG_COMMENT,
                                    JPG_SUBSMP,
                                    JPG_BASELINE,
                                    JPG_MARKERS,
                                    JPG_DCTALGO)

            elif CAPTCHA_FILE_EXT == ".png":
                gpdb.file_png_save2(img, drawable,
                                    imageTmp, imageTmp,
                                    PNG_INTERLACE,
                                    PNG_COMPRESSION,
                                    PNG_BKGD,
                                    PNG_GAMA,
                                    PNG_OFFSET,
                                    PNG_PHYS,
                                    PNG_TIME,
                                    PNG_COMMENT,
                                    PNG_SVGTRANS)

            else:
                return SystemExit("Image extension %r is not supported!"
                                  % CAPTCHA_FILE_EXT)
        except Exception as err:
            print(err)
            if os.path.isfile(imageTmp):
                os.unlink(imageTmp)
        else:
            os.rename(imageTmp, imagePath)


# Gimp-python boilerplate.
gimpfu.register('captcha_generate',
                'Generate CAPTCHAs',
                'Generate CAPTCHAs',
                'Isis Lovecruft',
                'Isis Lovecruft',
                '2014',
                '<Toolbox>/Xtns/Make-Captcha', '',
                [(gimpfu.PF_STRING, 'basedir', 'base directory for images', ''),
                 (gimpfu.PF_INT, 'count', 'number of images to add', 0)],
                [], captcha_generate)
gimpfu.main()
