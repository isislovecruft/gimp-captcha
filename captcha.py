#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#NOTE!: the interpreter line above MUST run whichever python version
#your installation's gimp-python support is compiled with. ensure that this
#corresponds, or nothing here will work.

'''
A Command Line Interface for Captcha Generation with Gimp

To use this script, place it in a gimp plug-ins directory and make it
executable. On Ubuntu Edgy this can be: $HOME/.gimp-2.2/plug-ins/

Invoke gimp like so:
gimp --no-interface --no-data --console-messages \
    --batch-interpreter plug_in_script_fu_eval \
    --batch '(python-fu-captcha-generate 1 "PATH" GOAL)' \
    '(gimp-quit 1)'

Goal is a number of captchas to put in the directory specified by
path. The directory will be "filled" to the goal level with pngs named
like answer.png, where answer is the string pictured in the image.

'''

# ===================================================================
# The first part of this file is the gimp scripting, meat of the
# solution.
# ===================================================================

import random
import gimpfu
import gimpplugin
from gimpfu import gimp, pdb as gpdb, \
    RGB_IMAGE, GRAY_IMAGE, GRAY, NORMAL_MODE, \
    MULTIPLY_MODE, WHITE_FILL, TRANSPARENT_FILL, FALSE, PIXELS, \
    TRANSFORM_FORWARD, INTERPOLATION_CUBIC, HISTOGRAM_VALUE, CLIP_TO_IMAGE
from gimpenums import PLUGIN, EXTENSION, PDB_INT32

def pick_font(fonts):
    '''Pick a font at random.'''
    # Using only "roman" or "oblique" fonts should help a lot. Italics
    # introduce a lot of problems like a's that look like o's etc.
    #
    # Future experiment: Return a list of fonts such that no two
    # adjacent letters share a font. random.suffle maybe?

    return random.choice(fonts)

def make_captcha(sx, sy, font_height, letter_spacing, left_margin,
                 angle_range, fonts, answer):
    '''Generate a captcha consisting of the letters in answer.

    Returns the captcha as a gimp-python image object.
    '''
    img = gimp.Image(sx, sy, RGB_IMAGE)
    img.disable_undo()

    # Start with a layer of noise, but not too much, as this will be
    # the background.
    light_noise_layer = gimp.Layer(img, 'light noise',
                                   sx, sy, RGB_IMAGE,
                                   100, NORMAL_MODE)
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
    gpdb.plug_in_scatter_hsv(img, light_noise_layer, 1, 25, 180, 180)
    #gpdb.plug_in_randomize_hurl(img,light_noise_layer,1, 1, 0, 0)
    gpdb.plug_in_gauss_iir(img, light_noise_layer, 1, 1, 1)
    gpdb.gimp_desaturate(light_noise_layer)


    # Next make pure black layer which we will copy repeatedly as a
    # place to cut out letters.
    black_layer = gimp.Layer(img, 'black',
                             sx, sy, RGB_IMAGE,
                             100, NORMAL_MODE)
    img.add_layer(black_layer, 0)
    black_layer.add_alpha()
    gpdb.gimp_layer_add_alpha(black_layer)
    gpdb.gimp_drawable_fill(black_layer, WHITE_FILL)
    gpdb.gimp_invert(black_layer)

    # Loop through each letter, making it a separate black layer.
    right = left_margin
    last_substrate = None
    for letter in answer:
        substrate_layer = black_layer.copy()
        img.add_layer(substrate_layer, 0)
        font = pick_font(fonts)
        new_right = \
            cookie_cutter_letter(img, substrate_layer, font_height,
                                 letter_spacing, angle_range, right, font,
                                 letter)
        # look out for really narrow letters
        if new_right - right < 10:
            new_right += 10
        right = new_right

    img.remove_layer(black_layer)
    #gimp.delete(black_layer)

    # Hide the light noise layer, then collapse all the remaining
    # layers (all letters) into a single layer.
    light_noise_layer.visible = False
    text_layer = gpdb.gimp_image_merge_visible_layers(img, CLIP_TO_IMAGE)
    light_noise_layer.visible = True

    # We aren't doing any letter warping now, but if we were, this is
    # the point where it should be done. We want to warp the shape of
    # the text layer which later serves as a cutout for the dark noise
    # layer. If we warp the dark noise layer directly we will end up
    # with warped dots.

    # Create a layer of dark noise which will display the letters.
    dark_noise_layer = gimp.Layer(img, 'dark noise',
                                  sx, sy, RGB_IMAGE,
                                  100, MULTIPLY_MODE)
    img.add_layer(dark_noise_layer, 1)
    gpdb.gimp_drawable_fill(dark_noise_layer, WHITE_FILL)
    gpdb.plug_in_randomize_hurl(img, dark_noise_layer, 25, 1, 0, 0)
    gpdb.gimp_desaturate(dark_noise_layer)

    # These next operations are ordered carefully. Changing the order
    # dramatically affects how the output looks.

    # Here's where we do the cutout operation.
    gpdb.gimp_selection_layer_alpha(text_layer)
    gpdb.gimp_selection_invert(img)
    gpdb.gimp_edit_clear(dark_noise_layer)
    gpdb.gimp_selection_none(img)

    # Do the blurring of the dark noise _after_ the cutout.
    gpdb.plug_in_gauss_iir(img, dark_noise_layer, 1, 1, 1)

    # Darken _after_ blurring.
    gpdb.gimp_levels(dark_noise_layer, HISTOGRAM_VALUE, 127, 255, 0.25, 0, 255)

    text_layer.visible = False

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

def cookie_cutter_letter(img, substrate_layer, font_height, letter_spacing,
                         angle_range, right, font, letter):
    '''Cut text shaped like letter out of the given layer.'''
    temp_layer = gpdb.gimp_text_fontname(img, substrate_layer, right, 0,
                                         letter, 1,
                                         False, font_height, PIXELS, font)

    # Future experiment: mess with the y offset. For now just assume
    # zero.  We get a little variation for free because we center our
    # rotation on the upper left corner of the letter.

    angle = random.uniform(*angle_range)
    #img.add_layer(temp_layer, 0)
    gpdb.gimp_selection_layer_alpha(temp_layer)

    # We need to save the selection as a channel so we can mess with
    # the letter form.
    text_shape = gpdb.gimp_selection_save(img)
    gpdb.gimp_selection_none(img)
    #img.add_channel(text_shape, 2)
    gpdb.gimp_floating_sel_remove(temp_layer)

    # Here's where we distore an individual letter form.
    gpdb.gimp_drawable_transform_rotate(text_shape, angle, 0, right, 10,
                                        TRANSFORM_FORWARD,
                                        INTERPOLATION_CUBIC,
                                        1, 3, 0)
    #gimp.delete(temp_layer)

    gpdb.gimp_selection_load(text_shape)
    img.remove_channel(text_shape)
    #gimp.delete(text_shape)

    # Note the bounding box of the letter form so we can figure out
    # where the next one should go.
    bounds = gpdb.gimp_selection_bounds(img)
    new_right = bounds[3] + letter_spacing

    # Actually cut the letter form out of the substate.
    gpdb.gimp_selection_invert(img)
    gpdb.gimp_edit_clear(substrate_layer)
    gpdb.gimp_selection_none(img)
    return new_right

# ===================================================================
# The second part of this file implements the gimp plugin goo.
#
# It would be simpler if we could just run our own python process and
# import libgimp or something, but unfortunately the gimp-python
# libraries can't function unless they are in communication with a
# running instance of the gimp.
# ===================================================================

import sys
import os
from tempfile import mkstemp

def select_answer(length):
    '''Select length charaters to form a string.

    The alphabet is carefully chosen to contain few similar letter
    shapes in roman fonts.
    '''
    # Remove characters to reduce confusion. No l, or o, for instance,
    # as running them together might look like b or d.
    alphabet = 'abdefgjknpqtuvxyz278'
    answer = ''
    for letter in random.sample(alphabet, length):
        answer += letter
    return answer

def count_images(image_dir):
    '''Count the png images in a directory.'''
    return len([ f for f in os.listdir(image_dir)
                 if f.endswith('.png') ])

def captcha_generate(image_dir, goal):
    '''Make sure there are as many catchas in image_dir as goal.'''
    needed = goal - count_images(image_dir)
    if needed < 1:
        return

    answers = [ select_answer(5) for i in xrange(0, needed) ]
    for answer in answers:
        image_path = os.path.join(image_dir, '%s.png' % answer)
        tmp_image_path = '%s.tmp' % image_path

        # Maybe these could be derived from the command line also.
        # Units are generally in pixels.

        image_width = 400
        image_height = 100
        font_height = 80
        letter_spacing = -12
        left_margin = 50

        # Rotate individual letters, in radians:
        angle_range = (-0.15, 0.15)

        fonts = ['Sans', 'Serif', 'Monospace', 'Serif Bold']

        # XXX: handle exceptions by unlinking bad images?
        img, drawable = make_captcha(image_width, image_height,
                                     font_height, letter_spacing,
                                     left_margin, angle_range, fonts,
                                     answer)
        gpdb.file_png_save2(img, drawable,
                            tmp_image_path, tmp_image_path,
                            0, 9, 0, 0, 0, 0, 0, 1, 0)
        os.rename(tmp_image_path, image_path)


# Gimp-python boilerplate.
gimpfu.register('captcha_generate', '', '', '', '', '',
                '<Toolbox>/Xtns/Make-Captcha', '',
                [(gimpfu.PF_STRING, 'basedir', 'base directory for images', ''),
                 (gimpfu.PF_INT, 'count', 'number of images to add', 0)],
                [], captcha_generate)
gimpfu.main()
