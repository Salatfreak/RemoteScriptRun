bl_info = {
    "name": "Remote Script Run",
    "description": "Allow reloading and executing scripts remotely",
    "author": "Salatfreak",
    "version": (0, 1),
    "blender": (2, 65, 0),
    "location": "Text Editor > Start remote",
    "wiki_url": "https://github.com/",
    "tracker_url": "https://github.com/",
    "category": "Text Editor"
}

# Import libraries
import os
import sys
import threading
import queue
import time
import bpy
import importlib
import addon_utils
import traceback

######################
# Main functionality #
######################

# Handle command
def handle_command(context, op, path):
    try:
        if op == 'reload_script':
            if reload_script(context, path):
                return ({'INFO'}, "Reloaded %s"%bpy.path.basename(path))
        elif op == 'run_script':
            if run_script(context, path):
                return ({'INFO'}, "Ran %s"%bpy.path.basename(path))
        elif op == 'reload_addon':
            if reload_addon(context, path):
                return ({'INFO'}, "Reloaded %s"%bpy.path.basename(path))
    except Exception as e:
        return ({'ERROR'}, traceback.format_exc())

# Reload text
def reload_script(context, path):
    text = get_text(path)
    if text is None: return False

    # Reload
    type_backup = context.area.type
    context.area.type = 'TEXT_EDITOR'
    bpy.ops.text.reload({
        'window': context.window,
        'scree': context.screen,
        'area': context.area,
        'region': context.region,
        'edit_text': text
    })
    context.area.type = type_backup
    
    return True

# Run script
def run_script(context, path):
    text = get_text(path)
    if text is None: return False

    # Execute text
    bpy.ops.text.run_script({
        'window': context.window,
        'screen': context.screen,
        'area': context.area,
        'region': context.region,
        'blend_data': context.blend_data,
        'edit_text': text
    })
    return True

# Reload add-on
def reload_addon(context, name):
    if not name in (m.__name__ for m in addon_utils.modules()): return False

    # Disable addon
    if name in context.user_preferences.addons.keys():
        addon_utils.disable(name)
    
    # Remove sub modules
    mod_names = list(filter(lambda m: m.startswith(name), sys.modules))
    mod_names.sort()
    for mod_name in mod_names:
        try: importlib.reload(importlib.import_module(mod_name))
        except AttributeError: pass

    # Enable addon
    addon_utils.enable(name)
    
    return True

###############
# Preferences #
###############

class RemoteScriptRunPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    pipe_directory = bpy.props.StringProperty(
        name="Pipe Directory",
        subtype="FILE_PATH",
        default="${tmp}"
    )

    def draw(self, context):
        self.layout.prop(self, "pipe_directory")
        self.layout.label(
            text="Variables: ${tmp}: Blender instances temporary directory, "
            "${home}: User directory"
        )
        self.layout.label("(takes effect after starting remote)")

#############
# Operators #
#############

# Modal execution operator
class RemoteScriptRunOperator(bpy.types.Operator):
    # Blender attributes
    bl_idname = "text.remote_script_run"
    bl_label = "Remote script running"
    
    # Properties
    stop = bpy.props.BoolProperty(default=False, options=set())

    # Execution handler
    def execute(self, context):
        if self.stop:
            return {'FINISHED'} if self.stop_running() else {'CANCELLED'}
        else:
            if self.is_running() or self.should_stop(): return {'CANCELLED'}
        
            # Start thread
            prefs = context.user_preferences.addons[__name__].preferences
            fifo_path = os.path.join(
                prefs.pipe_directory.replace(
                    "${tmp}", bpy.app.tempdir
                ).replace(
                    "${home}", os.path.expanduser("~")
                ),
                "script_run_pipe"
            )
            try:
                self._thread = PipeListenThread(fifo_path)
            except IOError:
                self.report({'ERROR'}, "Creating unix pipe failed")
                return {'CANCELLED'}
            self._thread.start()
            
            # Register modal operator
            context.window_manager.modal_handler_add(self)
            self._timer = context.window_manager.event_timer_add(0.1, context.window)
            
            # Set state to running
            self._set_running(True)

            # Return finished
            self._redraw(context)
            return {'RUNNING_MODAL'}
    
    # Modal handler
    def modal(self, context, event):
        if event.type == 'TIMER':
            # Stop operator if thread died
            if not self._thread.isAlive():
                context.window_manager.event_timer_remove(self._timer)
                self._set_running(False)
                self.report({'ERROR'}, "Command listening thread died")
                self._redraw(context)
                return {'CANCELLED'}
            # Stop operator if requested
            elif self.should_stop():
                context.window_manager.event_timer_remove(self._timer)
                self._thread.stop()
                self._set_running(False)
                self._redraw(context)
                return {'FINISHED'}
            # Get commands and execute them
            else:
                while self._thread.has_next():
                    command = self._thread.next()
                    if " " in command:
                        op, path = command.split(" ", 1)
                        message = handle_command(context, op, path)
                        if message is not None: self.report(*message)
                    
        return {'PASS_THROUGH'}
    
    def _redraw(self, context):
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR': area.tag_redraw()
    
    # Stop thread on forced stop
    def __del__(self):
        if hasattr(self, '_thread') and self._thread.isAlive():
            self._thread.stop()
        
    # Static state
    _RUNNING = False
    _SHOULD_STOP = False
    
    @classmethod
    def is_running(cls):
        return cls._RUNNING
    
    @classmethod
    def _set_running(cls, running):
        cls._RUNNING = running
        if not running: cls._SHOULD_STOP = False
                
    @classmethod
    def should_stop(cls):
        return cls._SHOULD_STOP
    
    @classmethod
    def stop_running(cls):
        if not cls._RUNNING or cls._SHOULD_STOP: return False
        cls._SHOULD_STOP = True
        return True

##################
# User Interface #
##################

# Texteditor GUI
def operator_control_button(self, context):
    if not RemoteScriptRunOperator.is_running():
        self.layout.operator(
            RemoteScriptRunOperator.bl_idname,
            text="Start remote"
        ).stop = False
    elif RemoteScriptRunOperator.is_running() \
    and RemoteScriptRunOperator.should_stop():
        self.layout.label("Stopping remote...")
    else:
        self.layout.operator(
            RemoteScriptRunOperator.bl_idname,
            text="Stop remote"
        ).stop = True

###########
# Helpers #
###########

# Get text object
def get_text(filepath):
    return next((
        t for t in bpy.data.texts
        if bpy.path.abspath(t.filepath) == filepath
    ), None)

# Thread for pipe listening
class PipeListenThread(threading.Thread):
    # Initialize thread
    def __init__(self, fifo_path):
        super().__init__()
        self._queue = queue.Queue()
        self._stop_event = threading.Event()

        # Create fifo
        if os.path.exists(fifo_path): os.remove(fifo_path)
        os.mkfifo(fifo_path)
        self._fifo_path = fifo_path

        # Open fifo nonblockingly
        self._fifo = open(os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK))

    # Run thread
    def run(self):
        # Read lines from fifo and write to queue
        while not self.stopped():
            line = self._fifo.readline()
            while len(line) != 0:
                self._queue.put(line[:-1])
                line = self._fifo.readline()
            time.sleep(0.1)

    # Check for items in queue
    def has_next(self):
        return not self._queue.empty()

    # Get next item
    def next(self):
        return self._queue.get()
    
    # Set stop flag
    def stop(self):
        self._stop_event.set()
        self.join()
        self._fifo.close()
        os.remove(self._fifo_path)

    # Check stop flag
    def stopped(self):
        return self._stop_event.is_set()

##################
# Initialization #
##################

def register():
    bpy.utils.register_class(RemoteScriptRunOperator)
    bpy.utils.register_class(RemoteScriptRunPreferences)
    bpy.types.TEXT_HT_header.append(operator_control_button)

def unregister():
    RemoteScriptRunOperator.stop_running()
    bpy.utils.unregister_class(RemoteScriptRunOperator)
    bpy.utils.unregister_class(RemoteScriptRunPreferences)
    bpy.types.TEXT_HT_header.remove(operator_control_button)

if __name__ == "__main__":
    register()
