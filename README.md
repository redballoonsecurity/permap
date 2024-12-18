# Per Mapper (permap)
Author: Red Balloon Security

_Supports loading .per files into Binary Ninja._

## Description:

Supports loading .per files into Binary Ninja. Very similar to [svdmap](https://github.com/Vector35/svdmap) as it was used as a template for implementing this plugin.

## Usage

1. Open binary in Binary Ninja
2. Run `Import per info` command.
3. Select Per file.
4. New segments should now be automatically created for each peripheral along with the structure.

### Disable Comments

Comments can be displayed poorly in some instances so if that is the case you can turn comments off.

To _disable_ comments set `PERMapper.enableComments` to **false**.

## License

This plugin is released under a Apache-2.0 license.
## Metadata Version

2